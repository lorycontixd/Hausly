// ============================================================================
// POSTGRESQL FLEXIBLE SERVER — infra/modules/postgres.bicep
// ============================================================================
// WHAT IS THIS?
// Azure Database for PostgreSQL (Flexible Server) is a fully managed database.
// Azure handles: backups, patching, failover, scaling, monitoring.
// You just connect to it like any PostgreSQL server.
//
// WHY "FLEXIBLE SERVER" (not "Single Server")?
// Single Server is the old offering (being retired). Flexible Server is newer,
// cheaper, and has features like:
// - Built-in PgBouncer (connection pooling)
// - Same-zone or zone-redundant HA
// - Better start/stop control (save money during off-hours)
// - More granular compute/storage selection
//
// HOW IT WORKS:
// 1. Azure provisions a PostgreSQL instance in your region
// 2. You get a hostname: pg-hausly-dev.postgres.database.azure.com
// 3. Your app connects via: postgresql://user:pass@hostname:5432/hausly
// 4. Azure handles backups (7-35 days retention), auto-patching, monitoring
//
// MULTI-TENANCY STRATEGY:
// We use a SINGLE database for all households. Tenant isolation is done via:
// - Application level: every query filters by household_id
// - Database level: Row-Level Security (RLS) policies enforce isolation
// This is defined in Alembic migrations, not in this Bicep file.
//
// DEV vs PROD:
// - Dev: Burstable B1ms (1 vCore, 2GB RAM, 32GB storage, no HA)
//   → Cheapest option. ~€13-15/month. Can be stopped when not in use.
// - Prod: GeneralPurpose D2s_v3 (2 vCores, 8GB RAM, 128GB storage, zone-redundant HA)
//   → Production-grade. ~€100-120/month. Always available with automatic failover.
// ============================================================================

@description('Deployment environment')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region')
param location string

@description('Administrator login name')
@secure()
param administratorLogin string

@description('Administrator password')
@secure()
param administratorPassword string

// ─── TIER SELECTION ─────────────────────────────────────────────────────────
// SKU (Stock Keeping Unit) determines compute power and pricing.
//
// Burstable: Shares CPU with other tenants. Can "burst" above baseline briefly.
//            Great for dev workloads that are mostly idle with occasional spikes.
//
// GeneralPurpose: Dedicated CPU cores. Consistent performance.
//                 Required for production workloads.
//
// The 'tier' + 'name' combination selects the exact VM size:
// - Standard_B1ms: 1 vCore, 2GB RAM (~€13/month)
// - Standard_D2s_v3: 2 vCores, 8GB RAM (~€100/month)

var skuName = environment == 'dev' ? 'Standard_B1ms' : 'Standard_D2s_v3'
var skuTier = environment == 'dev' ? 'Burstable' : 'GeneralPurpose'
var storageSizeGB = environment == 'dev' ? 32 : 128
var backupRetentionDays = environment == 'dev' ? 7 : 35

// High Availability: In prod, if the primary server goes down, Azure
// automatically promotes a standby replica. Downtime: ~10-30 seconds.
// In dev, we skip this to save money (no standby = half the compute cost).
var haMode = environment == 'dev' ? 'Disabled' : 'ZoneRedundant'

// ─── RESOURCE: PostgreSQL Flexible Server ───────────────────────────────────
resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: 'pg-hausly-${environment}'
  location: location
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    // PostgreSQL version. 16 is the latest stable. Our docker-compose uses 16-alpine too.
    version: '16'

    // Administrator credentials. These are for the initial admin user.
    // In production, create separate users with limited permissions for the app.
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword

    // Storage configuration
    storage: {
      storageSizeGB: storageSizeGB
      // autoGrow: Automatically expands storage when it's getting full.
      // Prevents outages from full disks. Only grows, never shrinks.
      autoGrow: 'Enabled'
    }

    // Backup configuration
    backup: {
      backupRetentionDays: backupRetentionDays
      // Geo-redundant backup: copies backups to a paired region (e.g., West Europe → North Europe)
      // Protects against regional disasters. Unnecessary for dev.
      geoRedundantBackup: environment == 'dev' ? 'Disabled' : 'Enabled'
    }

    // High Availability configuration
    highAvailability: {
      mode: haMode
    }

    // Network: Public access for now. In production, you'd typically use
    // Private Endpoints to keep database traffic on Azure's private network.
    // For dev simplicity, we use firewall rules to restrict access.
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

// ─── RESOURCE: Firewall Rule — Allow Azure Services ─────────────────────────
// This special rule (0.0.0.0 → 0.0.0.0) allows other Azure services
// (like Container Apps) to connect. It does NOT open the server to the internet.
resource firewallAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ─── RESOURCE: PostgreSQL Configuration — PgBouncer ─────────────────────────
// PgBouncer is a connection pooler built into Flexible Server.
// WHY: PostgreSQL has a hard limit on concurrent connections (~100 for B1ms).
//      Each Container App instance opens multiple connections.
//      PgBouncer multiplexes many app connections over fewer server connections.
// MODES:
// - 'transaction': connections are returned to the pool after each transaction (recommended)
// - 'session': connections held for entire client session (less efficient)
resource pgBouncerEnabled 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgresServer
  name: 'pgbouncer.enabled'
  properties: {
    value: 'true'
    source: 'user-override'
  }
}

// ─── RESOURCE: Database ─────────────────────────────────────────────────────
// Creates the actual 'hausly' database on the server.
// The server is just the engine; you still need to create a database within it.
resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgresServer
  name: 'hausly'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
@description('PostgreSQL server FQDN (hostname for connection strings)')
output serverFqdn string = postgresServer.properties.fullyQualifiedDomainName

@description('PostgreSQL server name')
output serverName string = postgresServer.name

