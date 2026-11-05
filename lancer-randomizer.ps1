$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$applicationPath = Join-Path $projectDirectory 'dist\windows\OrreRandomizer\OrreRandomizer.exe'
try {
    $manifest = Join-Path $projectDirectory 'dist\SHA256SUMS.json'
    if (Test-Path -LiteralPath $manifest -PathType Leaf) {
        $release = [regex]::Match((Get-Content -LiteralPath $manifest -Raw), '"(pokemon-orre-randomizer|colosseum-randomizer)-([0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?)-windows-x64\.zip"\s*:')
        if ($release.Success) {
            $app = if ($release.Groups[1].Value -eq 'pokemon-orre-randomizer') { 'OrreRandomizer' } else { 'ColosseumRandomizer' }
            $versionedPath = Join-Path $projectDirectory ('dist\windows\{0}-{1}\{0}.exe' -f $app, $release.Groups[2].Value)
            if (Test-Path -LiteralPath $versionedPath -PathType Leaf) { $applicationPath = $versionedPath }
        }
    }
    if (Test-Path -LiteralPath $applicationPath -PathType Leaf) {
        # This is the interactive application window, so it must remain visible.
        Start-Process -FilePath $applicationPath -WorkingDirectory (Split-Path -Parent $applicationPath) -WindowStyle Normal
    } else {
        Push-Location -LiteralPath $projectDirectory
        try {
            python -m orre_randomizer
            if ($LASTEXITCODE -ne 0) {
                throw "Le demarrage Python a echoue (code $LASTEXITCODE)."
            }
        } finally { Pop-Location }
    }
} catch {
    Write-Host "Impossible de lancer Pokemon Orre Randomizer : $($_.Exception.Message)" -ForegroundColor Red
    [void](Read-Host 'Appuyez sur Entree pour fermer')
    exit 1
}
