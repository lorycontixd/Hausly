// ============================================================================
// LOG ANALYTICS WORKSPACE — infra/modules/log-analytics.bicep
// ============================================================================
// WHAT IS THIS?
// Log Analytics is Azure's centralized logging service. Think of it like a
// searchable database for all your application and infrastructure logs.
//
// WHY DO WE NEED IT?
// Container Apps REQUIRES a Log Analytics workspace — it's where all container
// stdout/stderr, HTTP access logs, and system events are stored. Without this,
// Container Apps deployment will fail.
//
// HOW DOES IT WORK?
// 1. Your Container App writes logs to stdout (like any Docker container)
// 2. Azure automatically ships those logs to this workspace
// 3. You query logs using KQL (Kusto Query Language) in the Azure Portal
// 4. You can set up alerts (e.g., "email me if error rate > 5%")
//
// DEV vs PROD:
// - Dev: Free tier (500MB/day ingestion limit, 7 day retention)
//   → Plenty for a solo developer. Zero cost.
// - Prod: PerGB2018 (pay per GB ingested, 30 day retention)
//   → No ingestion cap. Costs ~€2.76/GB. Usually €2-5/month for a small app.
// ============================================================================

@description('Deployment environment')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region')
param location string

// ─── TIER SELECTION ─────────────────────────────────────────────────────────
// The 'sku' (Stock Keeping Unit) determines the pricing tier.
// - 'Free': 500MB/day limit, 7 day retention. €0/month.
// - 'PerGB2018': pay-per-GB, configurable retention. ~€2.76/GB.

var sku = environment == 'dev' ? 'Free' : 'PerGB2018'
var retentionDays = environment == 'dev' ? 7 : 30

// ─── RESOURCE DEFINITION ────────────────────────────────────────────────────
// 'resource' is the Bicep keyword that declares an Azure resource.
// Format: resource <symbolic-name> '<resource-type>@<api-version>' = { ... }
//
// The @api-version tells Azure which schema to use for this resource type.
// Think of it like a library version — newer versions may have more features.

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-hausly-${environment}'
  location: location
  properties: {
    sku: {
      name: sku
    }
    retentionInDays: retentionDays
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
// Outputs expose values from this module to the parent (main.bicep).
// Container Apps needs the workspace ID and shared key to ship logs here.

@description('The resource ID of the Log Analytics workspace')
output workspaceId string = logAnalyticsWorkspace.id

@description('The customer ID (GUID) of the workspace — needed by Container Apps')
output customerId string = logAnalyticsWorkspace.properties.customerId

@description('The shared key for Log Analytics (used by Container Apps environment)')
output sharedKey string = logAnalyticsWorkspace.listKeys().primarySharedKey
