param([switch]$OneFile)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path $python)) { throw 'Run uv sync with Python 3.12 (64-bit) first.' }
& $python -c "import PyInstaller; assert PyInstaller.__version__ == '6.16.0'"
if ($LASTEXITCODE -ne 0) { throw 'Install build dependency: uv pip install --python .venv/Scripts/python.exe pyinstaller==6.16.0' }
$env:CALICOPET_ONEFILE = if ($OneFile) { '1' } else { '0' }
$mode = if ($OneFile) { 'onefile' } else { 'onedir' }
try {
    & $python -m PyInstaller --noconfirm --distpath "dist/$mode" --workpath "build/$mode" CalicoPet.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
} finally { Remove-Item Env:CALICOPET_ONEFILE -ErrorAction SilentlyContinue }
$exe = if ($OneFile) { "dist/$mode/CalicoPet.exe" } else { "dist/$mode/CalicoPet/CalicoPet.exe" }
$checkRoot = Join-Path $PSScriptRoot "build/verification/$mode"
New-Item -ItemType Directory -Force $checkRoot | Out-Null
# Copy outside the build tree and clear development paths before executing.
$isolated = Join-Path $checkRoot ((-join ([char[]](0x72ec,0x7acb,0x8fd0,0x884c,0x76ee,0x5f55))) + '-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $isolated | Out-Null
if ($OneFile) { Copy-Item $exe $isolated -Force }
else { Copy-Item "dist/$mode/CalicoPet/*" $isolated -Recurse -Force }
$report = Join-Path $checkRoot 'result.json'
$savedPath = $env:PATH
$savedPythonPath = $env:PYTHONPATH
$savedPlatform = $env:QT_QPA_PLATFORM
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYTHONPATH = ''
    $env:QT_QPA_PLATFORM = 'windows'
    $proc = Start-Process -FilePath (Join-Path $isolated 'CalicoPet.exe') -ArgumentList @('--release-check', "`"$report`"") -WorkingDirectory $isolated -WindowStyle Hidden -PassThru
    if (!$proc.WaitForExit(120000)) { $proc.Kill(); throw 'Release check timed out.' }
    if ($proc.ExitCode -ne 0 -or !(Test-Path $report)) { throw "Release check failed: $report" }
    $result = Get-Content $report -Raw -Encoding UTF8 | ConvertFrom-Json
    if (!$result.ok) { throw $result.error }
} finally {
    $env:PATH = $savedPath
    $env:PYTHONPATH = $savedPythonPath
    $env:QT_QPA_PLATFORM = $savedPlatform
}
$destination = Join-Path $PSScriptRoot "release/$mode/CalicoPet-Windows-v0.1.0"
New-Item -ItemType Directory -Force $destination | Out-Null
if ($OneFile) { Copy-Item $exe $destination -Force }
else { Copy-Item "dist/$mode/CalicoPet/*" $destination -Recurse -Force }
Get-ChildItem 'docs/*.txt' | Copy-Item -Destination $destination -Force
if (Get-ChildItem $destination -Recurse -Filter pet_state.json) { throw 'Save file must not be distributed.' }
$zip = Join-Path $PSScriptRoot $(if ($OneFile) { 'release/CalicoPet-Windows-v0.1.0-onefile.zip' } else { 'release/CalicoPet-Windows-v0.1.0.zip' })
Compress-Archive -Path $destination -DestinationPath $zip -Force
Get-FileHash $zip -Algorithm SHA256
Write-Output "Verified release: $zip"
