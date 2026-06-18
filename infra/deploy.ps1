# ============================================================================
# Hausly Infrastructure Deployment Script
# ============================================================================
# Usage:
#   ./infra/deploy.ps1 -Environment dev
#   ./infra/deploy.ps1 -Environment prod
#
# Prerequisites:
#   - Azure CLI installed (az --version)
#   - Logged in (az login)
#   - Subscription set (az account set --subscription <id>)
# ============================================================================

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dev', 'prod')]
    [string]$Environment,

    [Parameter(Mandatory = $false)]
    [string]$Location = 'westeurope',

    [Parameter(Mandatory = $false)]
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

# ─── Configuration ───────────────────────────────────────────────────────────
$resourceGroup = "hausly-${Environment}-rg"
$templateFile = "$PSScriptRoot/main.bicep"
$paramFile = "$PSScriptRoot/parameters/${Environment}.bicepparam"

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Hausly Infrastructure Deployment                           ║" -ForegroundColor Cyan
Write-Host "║  Environment: $Environment                                          ║" -ForegroundColor Cyan
Write-Host "║  Resource Group: $resourceGroup                        ║" -ForegroundColor Cyan
Write-Host "║  Region: $Location                                    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Check prerequisites ─────────────────────────────────────────────────────
Write-Host "[1/4] Checking prerequisites..." -ForegroundColor Yellow

$azVersion = az version --output json 2>$null | ConvertFrom-Json
if (-not $azVersion) {
    Write-Error "Azure CLI not found. Install from: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}
Write-Host "  Azure CLI: $($azVersion.'azure-cli')" -ForegroundColor Green

$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Error "Not logged in. Run: az login"
    exit 1
}
Write-Host "  Subscription: $($account.name)" -ForegroundColor Green
Write-Host ""

# ─── Create resource group if needed ─────────────────────────────────────────
Write-Host "[2/4] Ensuring resource group exists..." -ForegroundColor Yellow

$rgExists = az group exists --name $resourceGroup 2>$null
if ($rgExists -eq 'false') {
    Write-Host "  Creating resource group: $resourceGroup in $Location" -ForegroundColor White
    if (-not $WhatIf) {
        az group create --name $resourceGroup --location $Location --output none
    }
    Write-Host "  Created." -ForegroundColor Green
} else {
    Write-Host "  Resource group already exists." -ForegroundColor Green
}
Write-Host ""

# ─── Prompt for secure parameters ────────────────────────────────────────────
Write-Host "[3/4] Preparing deployment parameters..." -ForegroundColor Yellow

if (-not $env:POSTGRES_ADMIN_PASSWORD) {
    $securePassword = Read-Host -Prompt "  Enter PostgreSQL admin password" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $env:POSTGRES_ADMIN_PASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
}
Write-Host "  PostgreSQL password: ****" -ForegroundColor Green
Write-Host ""

# ─── Deploy ──────────────────────────────────────────────────────────────────
Write-Host "[4/4] Deploying infrastructure..." -ForegroundColor Yellow

$deployArgs = @(
    'deployment', 'group', 'create',
    '--resource-group', $resourceGroup,
    '--template-file', $templateFile,
    '--parameters', $paramFile,
    '--name', "hausly-${Environment}-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
    '--output', 'table'
)

if ($WhatIf) {
    Write-Host "  [WHAT-IF MODE] Would run:" -ForegroundColor Magenta
    Write-Host "  az $($deployArgs -join ' ')" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Running what-if analysis..." -ForegroundColor Magenta
    az deployment group what-if `
        --resource-group $resourceGroup `
        --template-file $templateFile `
        --parameters $paramFile
} else {
    Write-Host "  Starting deployment (this may take 5-15 minutes)..." -ForegroundColor White
    az @deployArgs

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
        Write-Host "  Deployment SUCCESSFUL!" -ForegroundColor Green
        Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Next steps:" -ForegroundColor White
        Write-Host "  1. Store secrets in Key Vault (see docs/infrastructure-setup.md)" -ForegroundColor White
        Write-Host "  2. Build and push Docker image to ACR" -ForegroundColor White
        Write-Host "  3. Run Alembic migrations against the new database" -ForegroundColor White
    } else {
        Write-Error "Deployment FAILED. Check the error messages above."
        exit 1
    }
}
