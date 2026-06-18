# ============================================================================
# Deploy API to Azure Container Apps
# ============================================================================
# Builds the Docker image in ACR and creates a new Container Apps revision.
#
# Usage:
#   ./infra/deploy-api.ps1
#   ./infra/deploy-api.ps1 -Environment prod
# ============================================================================

param(
    [ValidateSet('dev', 'prod')]
    [string]$Environment = 'dev'
)

$ErrorActionPreference = 'Stop'

$registry = "crhausly${Environment}"
$image = "hausly-api"
$tag = "latest"
$containerApp = "ca-hausly-${Environment}"
$resourceGroup = "hausly-${Environment}-rg"
$apiRoot = "$PSScriptRoot/../apps/api"

Write-Host "Deploying API to $containerApp ($Environment)" -ForegroundColor Cyan

# 1. Build & push image to ACR
Write-Host "`n[1/3] Building image in ACR..." -ForegroundColor Yellow
az acr build --registry $registry --image "${image}:${tag}" --target prod $apiRoot
if ($LASTEXITCODE -ne 0) { throw "ACR build failed" }
Write-Host "Image pushed." -ForegroundColor Green

# 2. Update Container App (creates new revision)
Write-Host "`n[2/3] Creating new Container Apps revision..." -ForegroundColor Yellow
az containerapp update --name $containerApp --resource-group $resourceGroup --image "${registry}.azurecr.io/${image}:${tag}"
if ($LASTEXITCODE -ne 0) { throw "Container App update failed" }
Write-Host "New revision active." -ForegroundColor Green

# 3. Verify
Write-Host "`n[3/3] Active revisions:" -ForegroundColor Yellow
az containerapp revision list --name $containerApp --resource-group $resourceGroup --output table

Write-Host "`nDeploy complete." -ForegroundColor Cyan
