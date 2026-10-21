$ErrorActionPreference = "Stop"

$projectPath = Join-Path $PSScriptRoot "CWBridge.csproj"
$publishPath = Join-Path $PSScriptRoot "publish"

dotnet publish $projectPath `
    --configuration Release `
    --runtime win-x64 `
    --self-contained true `
    --output $publishPath

if ($LASTEXITCODE -ne 0) {
    throw "CWBridge publish failed with exit code $LASTEXITCODE."
}

Copy-Item (Join-Path $PSScriptRoot "CodeWalker.Notice.txt") $publishPath -Force
Copy-Item (Join-Path $PSScriptRoot "SharpDX.LICENSE.txt") $publishPath -Force
