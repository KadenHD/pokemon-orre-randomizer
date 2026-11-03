param(
    [string]$PublicDirectory = (Join-Path $PSScriptRoot '..\dist\public'),
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$public = (Resolve-Path -LiteralPath $PublicDirectory).Path
$manifest = Get-Content -LiteralPath (Join-Path $public 'SHA256SUMS.json') -Raw | ConvertFrom-Json -AsHashtable
$archives = @($manifest.Keys | Where-Object { $_ -match '^pokemon-orre-randomizer-\d+\.\d+\.\d+-windows-x64\.zip$' })
if ($archives.Count -ne 1) { throw 'Expected one public Windows archive in SHA256SUMS.json.' }
$archiveName = $archives[0]
$version = [regex]::Match($archiveName, '\d+\.\d+\.\d+').Value
$archive = Join-Path $public $archiveName
$installerName = $archiveName.Replace('.zip', '-setup.exe')
$destination = Join-Path $public $installerName
if (Test-Path -LiteralPath $destination) { throw "Installer already exists: $destination" }
if ((Get-Item -LiteralPath $archive).Length -ne $manifest[$archiveName].bytes -or
    (Get-FileHash -LiteralPath $archive).Hash -ne $manifest[$archiveName].sha256) {
    throw 'The Windows archive does not match its manifest.'
}

$build = Join-Path $root 'build'
New-Item -ItemType Directory -Path $build -Force | Out-Null
$work = (New-Item -ItemType Directory -Path (Join-Path $build ('installer-' + [guid]::NewGuid()))).FullName
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{2EDE9291-8972-4361-9A05-3CC158B9D54B}_is1'
$silent = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
$oldPlatform = $env:QT_QPA_PLATFORM
try {
    $contents = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($entry in $contents.Entries) {
            if ($entry.FullName -notmatch '^OrreRandomizer/' -or $entry.FullName -match '(^|/)\.\.(/|$)|[\\:]' -or
                [IO.Path]::GetExtension($entry.FullName) -in @('.iso','.rvz','.gcm','.raw','.sav','.gci') -or
                $entry.FullName -match '/assets/game/') {
                throw "Unexpected Windows archive entry: $($entry.FullName)"
            }
        }
    } finally { $contents.Dispose() }
    $extract = Join-Path $work 'package'
    Expand-Archive -LiteralPath $archive -DestinationPath $extract
    $payload = Join-Path $extract 'OrreRandomizer'
    if (-not (Test-Path -LiteralPath (Join-Path $payload 'OrreRandomizer.exe') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $payload '_internal') -PathType Container)) {
        throw 'The public Windows archive is incomplete.'
    }

    $bootstrap = Join-Path $work 'innosetup-6.7.3.exe'
    $compilerDirectory = Join-Path $work 'compiler'
    Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $bootstrap
    if ((Get-FileHash -LiteralPath $bootstrap).Hash -ne '9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732') {
        throw 'The downloaded Inno Setup compiler does not match its pinned hash.'
    }
    $bootstrapLog = Join-Path $work 'compiler.log'
    $arguments = $silent + @('/SP-','/PORTABLE=1','/NOICONS', ('/DIR="' + $compilerDirectory + '"'), ('/LOG="' + $bootstrapLog + '"'))
    $setup = Start-Process -FilePath $bootstrap -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
    if ($setup.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $bootstrapLog) { Get-Content -LiteralPath $bootstrapLog -Tail 30 }
        throw "Inno Setup compiler extraction failed ($($setup.ExitCode))."
    }
    $compiler = Join-Path $compilerDirectory 'ISCC.exe'
    if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) { throw 'ISCC.exe was not found.' }
    & $compiler "/O$work" "/DPayloadDir=$payload" "/DReleaseVersion=$version" (Join-Path $PSScriptRoot 'windows-installer.iss')
    if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed ($LASTEXITCODE)." }
    $installer = Join-Path $work $installerName

    if ($SmokeTest) {
        if (Test-Path -LiteralPath $uninstallKey) { throw 'An existing per-user install is registered. Use a clean test environment.' }
        $install = Join-Path $work 'smoke install'
        $uninstaller = Join-Path $install 'unins000.exe'
        try {
            $arguments = $silent + @('/NOICONS', ('/DIR="' + $install + '"'))
            $test = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
            if ($test.ExitCode -ne 0) { throw "Installer smoke test failed ($($test.ExitCode))." }
            foreach ($file in (Get-ChildItem -LiteralPath $payload -File -Recurse)) {
                $relative = [IO.Path]::GetRelativePath($payload, $file.FullName)
                $target = Join-Path $install $relative
                if ((Get-FileHash -LiteralPath $target).Hash -ne (Get-FileHash -LiteralPath $file.FullName).Hash) {
                    throw "Installed file differs from the Windows ZIP: $relative"
                }
            }
            $env:QT_QPA_PLATFORM = 'offscreen'
            $report = Join-Path $work 'diagnostics.json'
            $arguments = @('--diagnostics', ('"' + $report + '"'))
            $app = Start-Process -FilePath (Join-Path $install 'OrreRandomizer.exe') -WorkingDirectory $install -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
            if ($app.ExitCode -ne 0) { throw "Installed app diagnostic failed ($($app.ExitCode))." }
            $diagnostics = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
            if (-not $diagnostics.successful -or -not $diagnostics.frozen -or $diagnostics.version -ne $version -or
                $diagnostics.images.Count -ne 0 -or $diagnostics.rom_opened -or $diagnostics.personal_preferences_opened) {
                throw 'Installed app diagnostic did not match the public edition.'
            }
        } finally {
            if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
                $removed = Start-Process -FilePath $uninstaller -ArgumentList $silent -Wait -PassThru -WindowStyle Hidden
                if ($removed.ExitCode -ne 0 -or (Test-Path -LiteralPath $uninstallKey) -or
                    (Test-Path -LiteralPath (Join-Path $install 'OrreRandomizer.exe'))) { throw 'Test uninstall failed.' }
            }
        }
        Write-Output 'Verified the installed files, app diagnostics, and uninstall.'
    }

    Move-Item -LiteralPath $installer -Destination $destination
    Get-FileHash -LiteralPath $destination
} finally {
    $env:QT_QPA_PLATFORM = $oldPlatform
    $owned = Get-Item -LiteralPath $work -Force
    if ($owned.FullName -ne $work -or $owned.Parent.FullName -ne $build -or
        ($owned.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        (Get-ChildItem -LiteralPath $work -Recurse -Force -Attributes ReparsePoint | Select-Object -First 1)) {
        throw 'Unexpected installer work directory.'
    }
    Remove-Item -LiteralPath $work -Recurse -Force
}
