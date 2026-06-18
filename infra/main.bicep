// ============================================================================
// MAIN ORCHESTRATOR — infra/main.bicep
// ============================================================================
// This is the entry point for deploying all Hausly Azure infrastructure.
//
// HOW BICEP WORKS:
// - Bicep is a declarative language: you describe WHAT you want, not HOW to create it.
// - Azure Resource Manager (ARM) reads your declaration and figures out the steps.
// - If a resource already exists with the same name, ARM updates it (idempotent).
// - Modules let you split resources into reusable files (like functions in code).
//
// HOW THIS FILE WORKS:
// - Declares parameters (inputs that change per environment)
// - Calls modules (each module deploys one Azure service)
// - Passes outputs between modules (e.g., Log Analytics ID → Container Apps)
// ============================================================================

targetScope = 'resourceGroup'
// ^ Tells Bicep this template deploys into an existing Resource Group.
//   (Alternative: 'subscription' to create resource groups themselves)

// ─── PARAMETERS ─────────────────────────────────────────────────────────────
// Parameters are inputs you provide at deploy time.
// They let the SAME template produce different results for dev vs prod.

@description('Deployment environment. Controls tier selection for all resources.')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region for all resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('PostgreSQL administrator login name.')
@secure()
param postgresAdminLogin string

@description('PostgreSQL administrator password. Must meet Azure complexity requirements.')
@secure()
param postgresAdminPassword string

// ─── NAMING CONVENTION ──────────────────────────────────────────────────────
// All resource names follow: {type-prefix}-hausly-{environment}
// Examples: kv-hauslyapp-dev, signalr-hausly-prod, ca-hausly-dev
// This prevents name collisions and makes resources easy to identify.

// ─── MODULE: Log Analytics Workspace ────────────────────────────────────────
// WHAT: A centralized logging and monitoring service.
// WHY FIRST: Container Apps REQUIRES a Log Analytics workspace to store its logs.
//            It must be created before Container Apps can reference it.
module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    environment: environment
    location: location
  }
}

// ─── MODULE: Key Vault ──────────────────────────────────────────────────────
// WHAT: A secure secret store (like a password manager for your app).
// WHY: Secrets (DB passwords, API keys) should never be in code or env vars.
//      Container Apps reads secrets from Key Vault at runtime via managed identity.
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVault'
  params: {
    environment: environment
    location: location
  }
}

// ─── MODULE: PostgreSQL Flexible Server ─────────────────────────────────────
// WHAT: Managed PostgreSQL database (Azure handles backups, patching, HA).
// WHY FLEXIBLE SERVER: It's Azure's modern PostgreSQL offering with better
//                      pricing, built-in PgBouncer, and more configuration options.
module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    environment: environment
    location: location
    administratorLogin: postgresAdminLogin
    administratorPassword: postgresAdminPassword
  }
}

// ─── MODULE: Azure SignalR Service ──────────────────────────────────────────
// WHAT: Managed WebSocket relay service.
// WHY: Our FastAPI backend can't host persistent WebSocket connections efficiently.
//      SignalR Service handles all client connections; we just push messages via REST API.
module signalr 'modules/signalr.bicep' = {
  name: 'signalr'
  params: {
    environment: environment
    location: location
  }
}

// ─── MODULE: Blob Storage ───────────────────────────────────────────────────
// WHAT: Object storage for files (receipt photos, profile pictures, etc.)
// WHY BLOB: Cheapest storage option. Pay only for what you store. No server needed.
module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    environment: environment
    location: location
  }
}

// ─── MODULE: Container Registry ─────────────────────────────────────────────
// WHAT: Private Docker image registry (like Docker Hub, but private and in Azure).
// WHY: Container Apps pulls our API Docker image from here. Keeps images private
//      and co-located with the compute (fast pulls, no egress costs).
module containerRegistry 'modules/container-registry.bicep' = {
  name: 'containerRegistry'
  params: {
    environment: environment
    location: location
  }
}

// ─── MODULE: Container Apps ─────────────────────────────────────────────────
// WHAT: Serverless container hosting (like a simpler Kubernetes).
// WHY: Scale-to-zero means €0 when idle. Auto-scales under load. No VM management.
// DEPENDS ON: Log Analytics (for logs), Key Vault (for secrets), ACR (for images)
module containerApps 'modules/container-apps.bicep' = {
  name: 'containerApps'
  params: {
    environment: environment
    location: location
    logAnalyticsCustomerId: logAnalytics.outputs.customerId
    logAnalyticsSharedKey: logAnalytics.outputs.sharedKey
    keyVaultName: keyVault.outputs.vaultName
    containerRegistryName: containerRegistry.outputs.registryName
    containerRegistryLoginServer: containerRegistry.outputs.loginServer
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
// Outputs are values produced by the deployment that you might need later
// (e.g., URLs to connect to, names for CLI commands).

@description('The FQDN of the deployed Container App (API URL).')
output apiUrl string = containerApps.outputs.appFqdn

@description('PostgreSQL server FQDN for connection strings.')
output postgresHost string = postgres.outputs.serverFqdn

@description('SignalR service hostname.')
output signalrHost string = signalr.outputs.hostname

@description('Storage account name.')
output storageAccountName string = storage.outputs.accountName

@description('Key Vault name for secret management.')
output keyVaultName string = keyVault.outputs.vaultName

@description('Container Registry login server.')
output acrLoginServer string = containerRegistry.outputs.loginServer
