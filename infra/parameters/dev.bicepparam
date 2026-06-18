// ============================================================================
// DEV ENVIRONMENT PARAMETERS — infra/parameters/dev.bicepparam
// ============================================================================
// This file provides the input values for deploying the DEV environment.
//
// HOW .bicepparam FILES WORK:
// - They're the modern replacement for .json parameter files
// - They reference the Bicep template they apply to (via 'using')
// - They provide strongly-typed parameter values
// - Secure parameters (passwords) are prompted at deploy time (not stored here!)
//
// DEPLOY WITH:
//   az deployment group create \
//     --resource-group hausly-dev-rg \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/dev.bicepparam
// ============================================================================

using '../main.bicep'

// The environment parameter drives all tier/SKU selections in every module.
// 'dev' = cheapest possible tiers: Free SignalR, Burstable B1ms Postgres,
// scale-to-zero Container Apps, LRS storage.
param environment = 'dev'

// PostgreSQL admin credentials.
// @secure() parameters are prompted interactively at deploy time.
// They are NEVER stored in the parameter file.
// For CI/CD, pass them via: --parameters postgresAdminLogin=hausly_admin postgresAdminPassword=$(SECRET)
param postgresAdminLogin = 'hausly_admin'

// This will be prompted at deploy time (never commit passwords!)
// Must meet Azure requirements: 8+ chars, mixed case, numbers, special chars
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD', '')
