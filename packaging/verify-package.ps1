param(
    [Parameter(Mandatory = $true)]
    [string]$Installer,

    [Parameter(Mandatory = $true)]
    [string]$CliExecutable
)

$ErrorActionPreference = "Stop"

foreach ($RequiredFile in @($Installer, $CliExecutable)) {
    if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
        throw "Package verification input is missing: $RequiredFile"
    }
}

$ManifestText = & $CliExecutable manifest
if ($LASTEXITCODE -ne 0) {
    throw "Video Studio CLI manifest command failed."
}
$Manifest = $ManifestText | ConvertFrom-Json

if ($Manifest.writesExternalSystems -ne $false) {
    throw "Package boundary verification failed: writesExternalSystems is not false."
}
if ($Manifest.capabilities.platformPublishing -ne $false) {
    throw "Package boundary verification failed: platform publishing is enabled."
}
if ($Manifest.capabilities.engagementActions -ne $false) {
    throw "Package boundary verification failed: engagement actions are enabled."
}
if ($Manifest.capabilities.accountControl -ne $false) {
    throw "Package boundary verification failed: account control is enabled."
}
if ($Manifest.capabilities.platformIndependentCreation -ne $true) {
    throw "Package boundary verification failed: platformIndependent is disabled."
}
if ($Manifest.durationPolicy.finalVideoSeconds.max -ne 60) {
    throw "Package boundary verification failed: finalVideoMaxSeconds is not 60."
}
if ($Manifest.durationPolicy.modelGenerationUnitMaxSeconds -ne 15) {
    throw "Package boundary verification failed: generationUnitMaxSeconds is not 15."
}

$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Installer
$HashPath = "$Installer.sha256"
"$($Hash.Hash.ToLower())  $([System.IO.Path]::GetFileName($Installer))" |
    Set-Content -Encoding ascii -NoNewline $HashPath

$ReportPath = Join-Path (Split-Path -Parent $Installer) "video-studio-package-verification.json"
$Report = [ordered]@{
    schema = "omniops.video_studio_package_verification.v1"
    status = "PASS"
    installer = [System.IO.Path]::GetFullPath($Installer)
    installerSha256 = $Hash.Hash.ToLower()
    productionCore = $Manifest.productionCore
    clients = $Manifest.clients
    writesExternalSystems = $Manifest.writesExternalSystems
    platformPublishing = $Manifest.capabilities.platformPublishing
    engagementActions = $Manifest.capabilities.engagementActions
    accountControl = $Manifest.capabilities.accountControl
    platformIndependent = $Manifest.capabilities.platformIndependentCreation
    finalVideoMaxSeconds = $Manifest.durationPolicy.finalVideoSeconds.max
    generationUnitMaxSeconds = $Manifest.durationPolicy.modelGenerationUnitMaxSeconds
}
$Report | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 $ReportPath

Write-Host "Verified $Installer"
