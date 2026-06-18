// ============================================================================
// PROD ENVIRONMENT PARAMETERS — infra/parameters/prod.bicepparam
// ============================================================================
// This file provides the input values for deploying the PROD environment.
//
// DIFFERENCES FROM DEV:
// - environment = 'prod' triggers production-grade tiers everywhere:
//   - Standard_S1 SignalR (1000 connections)
//   - GeneralPurpose D2s_v3 PostgreSQL (HA, geo-backups)
//   - Always-on Container Apps (min 1 replica)
//   - GRS Blob Storage (geo-redundant)
//
// DEPLOY WITH:
//   az deployment group create \
//     --resource-group hausly-prod-rg \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/prod.bicepparam
// ============================================================================

using '../main.bicep'

param environment = 'prod'

// Production database credentials — use a DIFFERENT password from dev!
param postgresAdminLogin = 'hausly_admin'
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD', '')
