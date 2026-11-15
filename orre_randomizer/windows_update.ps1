param([Parameter(Mandatory=$true)][string]$Request)
$ErrorActionPreference = 'Stop'
$work = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Request))
$status = Join-Path $work 'status.json'
$cancel = Join-Path $work 'cancel'
$errorCode = 'update_failed'
$committed = $false
$restored = $false
$ready = $false
$parentExited = $false
$changed = [Collections.Generic.List[string]]::new()
$backed = [Collections.Generic.List[string]]::new()
function Report([string]$state, [string]$code = '') {
    $temp = $status + '.tmp'
    [IO.File]::WriteAllText($temp, (@{state=$state; code=$code; version=$config.version} | ConvertTo-Json -Compress))
    Move-Item -LiteralPath $temp -Destination $status -Force
}
function SafeRelative([string]$name) {
    if ($name -notmatch '^(OrreRandomizer\.exe|_internal/[^:]+|docs/[^:]+|licenses/[^:]+|third-party-sources/[^:]+|README\.md|CHANGELOG\.md|RESEARCH\.md|CONTRIBUTING\.md|LICENSE|THIRD_PARTY_NOTICES\.md|requirements-build\.txt|build-edition\.json|build-versions\.json|update-files\.json|pokemon-orre-randomizer-[0-9]+\.[0-9]+\.[0-9]+-source\.zip)$' -or
        $name -match '[\\\x00-\x1f]' -or $name -match '\.(iso|rvz|gcm|raw|sav|gci|dtm|fsys|dol|rel)$') { throw ('Invalid package path: ' + $name) }
    foreach ($part in $name.Split('/')) {
        if ($part -in @('', '.', '..') -or $part -match '[. ]$' -or $part -match '^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\.|$)') { throw 'Invalid path component' }
    }
    return $name
}
function CheckPath([string]$root, [string]$name) {
    $relative = SafeRelative $name
    $current = $root
    foreach ($part in $relative.Split('/')) {
        $current = Join-Path $current $part
        if ((Test-Path -LiteralPath $current) -and ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse point refused' }
    }
    return $current
}
try {
    $config = Get-Content -LiteralPath $Request -Raw | ConvertFrom-Json
    $exe = [IO.Path]::GetFullPath($config.executable)
    $target = [IO.Path]::GetDirectoryName($exe)
    if ([IO.Path]::GetFileName($exe) -cne 'OrreRandomizer.exe' -or $target -eq [IO.Path]::GetPathRoot($target) -or
        $config.version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$' -or $config.kind -notin @('installer', 'portable')) { throw 'Invalid request' }
    # Check every ancestor, not merely the final executable or directory.
    $ancestor = Get-Item -LiteralPath $target -Force
    while ($null -ne $ancestor) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }
        $ancestor = $ancestor.Parent
    }
    $parentProcess = Get-Process -Id $config.parent
    if ($parentProcess.StartTime.ToFileTimeUtc().ToString() -ne $config.parent_started -or
        $parentProcess.MainModule.FileName -ine $exe) { throw 'Unexpected parent process' }
    $errorCode = 'running'
    foreach ($other in (Get-Process -Name OrreRandomizer -ErrorAction SilentlyContinue)) {
        if ($other.Id -ne $parentProcess.Id -and $other.MainModule.FileName -ieq $exe) { throw 'Another instance is running' }
    }
    $errorCode = 'disk'
    $probe = Join-Path $target ('.orre-write-' + [guid]::NewGuid())
    [IO.File]::WriteAllText($probe, '')
    [IO.File]::Delete($probe)
    $errorCode = 'checksum'
    $package = Get-Item -LiteralPath $config.package
    $hasher = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($package.FullName)
    try { $actualHash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $hasher.Dispose() }
    if ($package.DirectoryName -ine $work -or ($package.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        $package.Length -ne $config.size -or $config.sha256 -notmatch '^[a-f0-9]{64}$' -or
        $actualHash -ine $config.sha256) { throw 'Package integrity check failed' }
    $errorCode = 'package'
    $files = [Collections.Generic.List[string]]::new()
    $oldFiles = @()
    $stage = Join-Path $work 'staged'
    if ($config.kind -eq 'portable') {
        [void][Reflection.Assembly]::Load('System.IO.Compression.FileSystem, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089')
        $zip = [IO.Compression.ZipFile]::OpenRead($package.FullName)
        try {
            if ($zip.Entries.Count -gt 15000) { throw 'Too many entries' }
            $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
            [long]$total = 0
            foreach ($entry in $zip.Entries) {
                if ($entry.FullName -cnotlike 'OrreRandomizer/*') { throw 'Unexpected package root' }
                $relative = $entry.FullName.Substring(15)
                if ($relative.EndsWith('/')) { throw 'Unexpected directory entry' }
                $relative = SafeRelative $relative
                if (-not $seen.Add($relative) -or (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw 'Duplicate or linked entry' }
                $total += $entry.Length
                if ($total -gt 2147483648) { throw 'Package too large' }
                $existing = CheckPath $target $relative
                if (Test-Path -LiteralPath $existing -PathType Container) { throw 'File collides with a directory' }
                $files.Add($relative)
            }
            if (-not $seen.Contains('OrreRandomizer.exe') -or -not ($files | Where-Object { $_ -like '_internal/*' })) { throw 'Incomplete package' }
            foreach ($entry in $zip.Entries) {
                if (Test-Path -LiteralPath $cancel) { throw 'Cancelled' }
                $destination = CheckPath $stage $entry.FullName.Substring(15)
                [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination))
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $false)
            }
        } finally { $zip.Dispose() }
        $previousManifest = Join-Path $target 'update-files.json'
        if (Test-Path -LiteralPath $previousManifest) {
            $oldFiles = Get-Content -LiteralPath $previousManifest -Raw | ConvertFrom-Json
            if ($oldFiles.Count -gt 15000) { throw 'Invalid previous manifest' }
            foreach ($relative in $oldFiles) { [void](CheckPath $target $relative) }
        }
    }
    if (Test-Path -LiteralPath $cancel) { throw 'Cancelled' }
    Report 'ready'
    $ready = $true
    Write-Output 'Waiting for the verified application to exit.'
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while (-not $parentProcess.HasExited) {
        if (Test-Path -LiteralPath $cancel) { throw 'Cancelled' }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Parent did not exit' }
        Start-Sleep -Milliseconds 50
    }
    $parentExited = $true
    Write-Output 'Application exited; applying the verified package.'
    if (Test-Path -LiteralPath $cancel) { throw 'Cancelled' }
    $errorCode = 'update_failed'
    if ($config.kind -eq 'installer') {
        $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/NOCANCEL',
                       ('/DIR="' + $target + '"'), ('/LOG="' + (Join-Path $work 'installer.log') + '"'))
        $installInfo = [Diagnostics.ProcessStartInfo]::new()
        $installInfo.FileName = $package.FullName
        $installInfo.Arguments = $arguments -join ' '
        $installInfo.UseShellExecute = $false
        $installInfo.CreateNoWindow = $true
        $install = [Diagnostics.Process]::Start($installInfo)
        $install.WaitForExit()
        if ($install.ExitCode -ne 0) { throw 'Installer failed' }
    } else {
        $backup = Join-Path $target ('.orre-update-backup-' + [guid]::NewGuid())
        [void][IO.Directory]::CreateDirectory($backup)
        foreach ($relative in @($files.ToArray()) + $oldFiles | Select-Object -Unique) {
            $destination = CheckPath $target $relative
            if (Test-Path -LiteralPath $destination -PathType Leaf) {
                $saved = CheckPath $backup $relative
                [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($saved))
                [IO.File]::Move($destination, $saved)
                $backed.Add($relative)
            }
        }
        foreach ($relative in $files) {
            $destination = CheckPath $target $relative
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination))
            $changed.Add($relative)
            [IO.File]::Copy((Join-Path $stage $relative), $destination, $false)
        }
    }
    $committed = $true
    Report 'complete'
    Write-Output 'Update complete.'
} catch {
    Write-Output $_.Exception.ToString()
    if (-not $committed -and $config.kind -eq 'portable') {
        foreach ($relative in $changed) { [IO.File]::Delete((CheckPath $target $relative)) }
        foreach ($relative in $backed) { [IO.File]::Move((CheckPath $backup $relative), (CheckPath $target $relative)) }
        $restored = $true
    }
    Report 'error' $errorCode
} finally {
    if ($parentExited -and -not (Test-Path -LiteralPath $cancel) -and (Test-Path -LiteralPath $exe -PathType Leaf)) {
        # This is the only process restarted. No emulator or other window is touched.
        Write-Output 'Restarting the application.'
        $restartInfo = [Diagnostics.ProcessStartInfo]::new()
        $restartInfo.FileName = $exe
        $restartInfo.WorkingDirectory = $target
        $restartInfo.Arguments = '--update-result "' + $status + '"'
        $restartInfo.UseShellExecute = $false
        $restartInfo.CreateNoWindow = $true
        $restartInfo.EnvironmentVariables['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
        $restarted = [Diagnostics.Process]::Start($restartInfo)
        $restarted.Dispose()
    }
    if (($committed -or $restored) -and $backup -and (Test-Path -LiteralPath $backup)) {
        $resolved = Get-Item -LiteralPath $backup -Force
        if ($resolved.Parent.FullName -ieq $target -and $resolved.Name -like '.orre-update-backup-*' -and
            -not ($resolved.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Remove-Item -LiteralPath $backup -Recurse -Force }
    }
    # Keep only a small status/log after the helper exits, never a downloaded bundle.
    Write-Output 'Removing temporary package files.'
    foreach ($owned in @('package.zip', 'package.exe', 'staged')) {
        $path = Join-Path $work $owned
        if ((Test-Path -LiteralPath $path) -and [IO.Path]::GetDirectoryName($path) -eq $work) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
}
