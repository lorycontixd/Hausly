// ============================================================================
// CONTAINER REGISTRY — infra/modules/container-registry.bicep
// ============================================================================
// WHAT IS THIS?
// Azure Container Registry (ACR) is a private Docker image registry.
// Think of it like Docker Hub, but private, faster (same Azure network), and
// integrated with Container Apps for seamless image pulls.
//
// WHY DO WE NEED IT?
// Our FastAPI backend runs in a Docker container (see apps/api/Dockerfile).
// That container image needs to be stored somewhere Container Apps can pull it from.
// ACR provides:
// - Private storage (only our services can pull)
// - No egress costs (same Azure network)
// - Geo-replication for prod (fast pulls from any region)
// - Built-in vulnerability scanning
//
// HOW DOES DEPLOYMENT WORK?
// 1. CI/CD pipeline (or you manually) runs: az acr build --registry crhauslydev --image hausly-api:latest apps/api/
// 2. ACR builds the Docker image from the Dockerfile and stores it
// 3. Container Apps is configured to pull from ACR (using managed identity)
// 4. On each new image push, Container Apps can auto-update (continuous deployment)
//
// NAMING:
// ACR names must be globally unique, 5-50 chars, alphanumeric ONLY.
// No hyphens, no underscores. Hence: crhauslydev (not cr-hausly-dev).
//
// DEV vs PROD:
// - Dev: Basic (10GB storage, limited throughput). ~€5/month.
//   → Sufficient for a single image with a few versions.
// - Prod: Standard (100GB, higher throughput, geo-replication available). ~€20/month.
//   → More storage, webhooks for CI/CD, content trust.
// ============================================================================

@description('Deployment environment')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region')
param location string

// ─── TIER SELECTION ─────────────────────────────────────────────────────────
// SKUs:
// - Basic: 10GB, 2 webhooks. Good for dev/test.
// - Standard: 100GB, 10 webhooks, geo-rep available. Good for production.
// - Premium: 500GB, unlimited webhooks, geo-rep, private link. Enterprise.

var skuName = environment == 'dev' ? 'Basic' : 'Standard'

// ACR name: globally unique, alphanumeric only, 5-50 chars
var registryName = 'crhausly${environment}'

// ─── RESOURCE: Container Registry ───────────────────────────────────────────
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: {
    name: skuName
  }
  properties: {
    // Admin user: enables username/password auth for docker login.
    // We enable this for simplicity in dev. In prod, prefer managed identity.
    adminUserEnabled: true

    // Public network access: Allow pulls from anywhere (needed for local dev)
    publicNetworkAccess: 'Enabled'

    // Policies
    policies: {
      // Retention policy: auto-delete untagged manifests after N days.
      // Keeps the registry clean from dangling layers.
      retentionPolicy: {
        status: 'enabled'
        days: environment == 'dev' ? 7 : 30
      }
    }
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
@description('Container Registry name')
output registryName string = containerRegistry.name

@description('Container Registry login server (e.g., crhauslydev.azurecr.io)')
output loginServer string = containerRegistry.properties.loginServer
