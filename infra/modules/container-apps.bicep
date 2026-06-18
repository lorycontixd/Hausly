// ============================================================================
// CONTAINER APPS — infra/modules/container-apps.bicep
// ============================================================================
// WHAT IS THIS?
// Azure Container Apps is a serverless container hosting service.
// Think of it as "Kubernetes without the complexity" — you give it a Docker image,
// it runs it, scales it, and gives you a URL.
//
// WHY CONTAINER APPS (not App Service, not Functions, not AKS)?
// - vs App Service: Container Apps scales to ZERO (€0 when idle). App Service always has a minimum instance running.
// - vs Functions: Functions is for short-lived stateless invocations. We need persistent processes for WebSocket connections.
// - vs AKS (Kubernetes): AKS is complex, expensive, and overkill for a single service.
// - Container Apps gives us: scale-to-zero, HTTPS, custom domains, auto-scaling, and it's simple.
//
// ARCHITECTURE:
// Container Apps has 2 levels:
// 1. Environment: The shared infrastructure (networking, Log Analytics, etc.)
//    All apps in an environment share the same virtual network.
// 2. Container App: The actual running application (our FastAPI backend)
//    Each app can have multiple replicas (instances) for scaling.
//
// HOW SCALING WORKS:
// - minReplicas: Minimum instances always running (0 = scale to zero)
// - maxReplicas: Maximum instances under load
// - Scale rules: When to add/remove instances (e.g., HTTP requests/second)
//
// In dev: minReplicas=0 means €0 cost when nobody is using the API.
//         First request after idle takes ~5-10 seconds (cold start).
// In prod: minReplicas=1 means one instance is always warm. No cold starts.
//
// SECRETS & KEY VAULT:
// Container Apps can reference Key Vault secrets. At startup, it resolves
// the references and injects values as environment variables.
// This keeps secrets out of Bicep templates and deployment logs.
//
// DEV vs PROD:
// - Dev: 0.25 CPU, 0.5Gi RAM, 0 min replicas (scale to zero). ~€0-5/month.
// - Prod: 0.5 CPU, 1Gi RAM, 1 min replica (always warm). ~€15-30/month.
// ============================================================================

@description('Deployment environment')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region')
param location string

@description('Log Analytics workspace customer ID (GUID for log shipping)')
param logAnalyticsCustomerId string

@description('Log Analytics shared key (for auth)')
@secure()
param logAnalyticsSharedKey string

@description('Key Vault name (for secret references)')
param keyVaultName string

@description('Container Registry name')
param containerRegistryName string

@description('Container Registry login server (e.g., crhauslydev.azurecr.io)')
param containerRegistryLoginServer string

// ─── CONFIGURATION ──────────────────────────────────────────────────────────
// CPU and memory allocation per container instance.
// Container Apps uses a fractional CPU model:
// - 0.25 CPU = quarter of a core (minimum allowed)
// - 0.5 CPU = half a core
// Memory must be at least 2x the CPU value in Gi.

var cpu = environment == 'dev' ? '0.25' : '0.5'
var memory = environment == 'dev' ? '0.5Gi' : '1Gi'
var minReplicas = environment == 'dev' ? 0 : 1
var maxReplicas = environment == 'dev' ? 2 : 5

// ─── RESOURCE: Container Apps Environment ───────────────────────────────────
// The "environment" is the shared hosting infrastructure.
// All Container Apps within an environment:
// - Share the same virtual network
// - Share the same Log Analytics workspace
// - Can communicate internally via the environment's DNS
// You only need ONE environment per deployment (dev or prod).

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-hausly-${environment}'
  location: location
  properties: {
    // Log Analytics configuration: where container logs are shipped
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }

    // Workload profiles: 'Consumption' means pay-per-use, scale-to-zero capable.
    // Alternative: 'Dedicated' for fixed compute (more expensive, predictable).
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ─── RESOURCE: Container App (FastAPI Backend) ──────────────────────────────
// This is the actual running application. It pulls our Docker image from ACR
// and runs it with the specified CPU/memory/scaling configuration.

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-hausly-${environment}'
  location: location

  // Managed Identity: This gives the container app an "identity" in Azure AD.
  // The app can then authenticate to other Azure services (Key Vault, ACR)
  // WITHOUT storing any credentials. Azure handles the token exchange.
  identity: {
    type: 'SystemAssigned'
  }

  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    workloadProfileName: 'Consumption'

    configuration: {
      // Ingress: How external traffic reaches the app
      ingress: {
        external: true              // Accessible from the internet
        targetPort: 8000            // FastAPI listens on port 8000 (see Dockerfile)
        transport: 'http'           // Container Apps handles TLS termination for us
        allowInsecure: false        // Redirect HTTP → HTTPS automatically

        // CORS is handled by FastAPI middleware, not here.
        // Container Apps just forwards all traffic to the container.
      }

      // Registry: Where to pull the Docker image from
      registries: [
        {
          server: containerRegistryLoginServer
          // Using admin credentials for simplicity.
          // In production, prefer managed identity with acrPull role.
          username: containerRegistryName
          passwordSecretRef: 'acr-password'
        }
      ]

      // Secrets: Values that Container Apps injects as env vars.
      // These are stored encrypted and never exposed in logs.
      secrets: [
        {
          name: 'acr-password'
          // Reference the ACR admin password.
          // In a real setup, you'd use Key Vault references here.
          value: listCredentials(resourceId('Microsoft.ContainerRegistry/registries', containerRegistryName), '2023-07-01').passwords[0].value
        }
      ]
    }

    template: {
      containers: [
        {
          name: 'hausly-api'
          // Image reference: registry/image:tag
          // Initially uses a placeholder. CI/CD will update this.
          image: '${containerRegistryLoginServer}/hausly-api:latest'
          resources: {
            cpu: json(cpu)    // json() converts string '0.25' to number 0.25
            memory: memory
          }

          // Environment variables injected into the container.
          // Non-sensitive values go directly here.
          // Sensitive values reference the 'secrets' array above.
          env: [
            {
              name: 'ENVIRONMENT'
              value: environment
            }
            {
              name: 'PORT'
              value: '8000'
            }
            {
              // Tell the app where Key Vault is, so it can fetch secrets at startup
              name: 'KEY_VAULT_NAME'
              value: keyVaultName
            }
          ]
        }
      ]

      // Scaling rules: When to add/remove instances
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                // Add a new instance when an existing one handles >30 concurrent requests
                concurrentRequests: '30'
              }
            }
          }
        ]
      }
    }
  }
}

// ─── ROLE ASSIGNMENT: Key Vault Secrets User ────────────────────────────────
// Grant the Container App's managed identity permission to READ secrets from Key Vault.
// Role: "Key Vault Secrets User" (4633458b-17de-408a-b874-0445c86b69e6)
// This follows the principle of least privilege: read-only, no write/delete.

resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerApp.id, keyVaultName, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
@description('Container App FQDN (the public URL of our API)')
output appFqdn string = containerApp.properties.configuration.ingress.fqdn

@description('Container App resource ID')
output appResourceId string = containerApp.id

@description('Container App managed identity principal ID (for role assignments)')
output appPrincipalId string = containerApp.identity.principalId

