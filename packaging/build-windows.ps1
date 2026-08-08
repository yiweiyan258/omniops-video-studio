param(
    [Parameter(Mandatory = $true)]
    [string]$WorkbenchExecutable,

    [Parameter(Mandatory = $true)]
    [string]$FfmpegExecutable,

    [Parameter(Mandatory = $true)]
    [string]$FfprobeExecutable,

    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
    throw "The Setup.exe build must run on Windows x64."
}

$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProjectRoot = (Resolve-Path (Join-Path $AppRoot "../..")).Path
$BuildRoot = Join-Path $AppRoot ".build"
$VenvRoot = Join-Path $BuildRoot "venv"
$BinaryRoot = Join-Path $AppRoot "src-tauri/binaries"
$TargetTriple = "x86_64-pc-windows-msvc"
$DistRoot = if ($OutputDirectory) {
    [System.IO.Path]::GetFullPath($OutputDirectory)
} else {
    Join-Path $AppRoot "dist"
}
$InstallerOutput = Join-Path $DistRoot "OmniOpsVideoStudio-Setup-x64.exe"

foreach ($RequiredFile in @(
    $WorkbenchExecutable,
    $FfmpegExecutable,
    $FfprobeExecutable
)) {
    if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
        throw "Required runtime component is missing: $RequiredFile"
    }
}

$WorkbenchDoctorText = & $WorkbenchExecutable doctor --format json
if ($LASTEXITCODE -ne 0) {
    throw "Canonical workbench doctor failed."
}
$WorkbenchDoctor = $WorkbenchDoctorText | ConvertFrom-Json
$Compatibility = $WorkbenchDoctor.videoStudioCompatibility
if (
    $Compatibility.platformIndependent -ne $true -or
    $Compatibility.finalVideoMaxSeconds -ne 60 -or
    $Compatibility.generationUnitMaxSeconds -ne 15
) {
    throw "Canonical workbench is missing the Video Studio 0.2 duration contract."
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $BinaryRoot, $DistRoot | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $VenvRoot "Scripts/python.exe"))) {
    python -m venv $VenvRoot
}
$Python = Join-Path $VenvRoot "Scripts/python.exe"
& $Python -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot "requirements-build.txt")
& $Python -m PyInstaller --clean --noconfirm (Join-Path $PSScriptRoot "video-studio-cli.spec")

$CliBuilt = Join-Path $AppRoot "dist/omniops-video-studio-cli.exe"
if (-not (Test-Path -LiteralPath $CliBuilt -PathType Leaf)) {
    throw "PyInstaller did not create omniops-video-studio-cli.exe"
}

Copy-Item -Force $CliBuilt (Join-Path $BinaryRoot "omniops-video-studio-cli-$TargetTriple.exe")
Copy-Item -Force $WorkbenchExecutable (Join-Path $BinaryRoot "omniops-video-workbench-$TargetTriple.exe")
Copy-Item -Force $FfmpegExecutable (Join-Path $BinaryRoot "ffmpeg-$TargetTriple.exe")
Copy-Item -Force $FfprobeExecutable (Join-Path $BinaryRoot "ffprobe-$TargetTriple.exe")

Push-Location $AppRoot
try {
    npm ci
    npm run tauri:build:windows
} finally {
    Pop-Location
}

$GeneratedInstaller = Get-ChildItem `
    -Path (Join-Path $AppRoot "src-tauri/target/release/bundle/nsis") `
    -Filter "*.exe" `
    | Sort-Object LastWriteTime -Descending `
    | Select-Object -First 1
if (-not $GeneratedInstaller) {
    throw "Tauri did not create an NSIS installer."
}

Copy-Item -Force $GeneratedInstaller.FullName $InstallerOutput
& (Join-Path $PSScriptRoot "verify-package.ps1") `
    -Installer $InstallerOutput `
    -CliExecutable $CliBuilt

Write-Host "Created $InstallerOutput"
