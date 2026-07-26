$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Venv = Join-Path $ProjectRoot ".venv-windows-build"
$Python = Join-Path $Venv "Scripts\python.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"
$Spec = Join-Path $PSScriptRoot "JellyfinMigrationAssistant.spec"
$BuildDir = Join-Path $ProjectRoot "build\windows"
$DistDir = Join-Path $ProjectRoot "dist\windows"

Set-Location $ProjectRoot

if (!(Test-Path $Python)) {
    py -3 -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install . pyinstaller
$PyInstallerCommand = "`"$PyInstaller`" --clean --noconfirm --workpath `"$BuildDir`" --distpath `"$DistDir`" `"$Spec`" 2>&1"
$PyInstallerOutput = cmd.exe /c $PyInstallerCommand
$PyInstallerExit = $LASTEXITCODE
$PyInstallerOutput | ForEach-Object { Write-Host $_ }
if ($PyInstallerExit -ne 0) {
    throw "PyInstaller failed with exit code $PyInstallerExit"
}

$Exe = Join-Path $DistDir "JellyfinMigrationAssistant.exe"
if (!(Test-Path $Exe)) {
    throw "Expected executable was not built: $Exe"
}

Write-Host "Built $Exe"
