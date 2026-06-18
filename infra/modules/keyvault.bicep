// ============================================================================
// KEY VAULT — infra/modules/keyvault.bicep
// ============================================================================
// WHAT IS THIS?
// Azure Key Vault is a managed secret store. It's like a password manager,
// but for your application's secrets (database URLs, API keys, etc.).
//
// WHY DO WE NEED IT?
// Secrets should NEVER be:
// - Hardcoded in source code (anyone with repo access sees them)
// - Stored in environment variables in Bicep (they appear in deployment logs)
// - Baked into Docker images (anyone with image access sees them)
//
// Instead, secrets live in Key Vault. At runtime, Container Apps reads them
// using a "managed identity" (a passwordless Azure identity assigned to the app).
//
// HOW DOES IT WORK?
// 1. Secrets are stored in Key Vault (manually or via CI/CD pipeline)
// 2. Container App has a "managed identity" (like a service account)
// 3. We grant that identity "Key Vault Secrets User" role (read-only)
// 4. Container App references secrets like: keyVaultUrl: 'https://kv-hausly-dev.vault.azure.net/secrets/DATABASE-URL'
// 5. At startup, Container Apps resolves the reference and injects the value
//
// SECURITY MODEL:
// - enableRbacAuthorization: true → Uses Azure RBAC (role-based access control)
//   instead of vault-level access policies. This is the modern approach.
// - The app can only READ secrets, never write/delete them.
// - Only the deployment pipeline (or a human admin) can write secrets.
//
// DEV vs PROD:
// Both use the Standard SKU (the only practical option — Premium adds HSM
// support which we don't need). Pricing is per-operation (~€0.03/10K operations).
// ============================================================================

@description('Deployment environment')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region')
param location string

// ─── RESOURCE DEFINITION ────────────────────────────────────────────────────
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-hausly-${environment}'
  location: location
  properties: {
    // Standard SKU: software-protected keys. ~€0.03/10K operations.
    // Premium SKU: HSM-backed keys. We don't need hardware security modules.
    sku: {
      family: 'A'
      name: 'standard'
    }

    // tenantId: Identifies which Azure AD tenant owns this vault.
    // subscription().tenantId gets the tenant of the current Azure subscription.
    tenantId: subscription().tenantId

    // RBAC authorization: Modern approach. Access is controlled by Azure roles
    // (e.g., "Key Vault Secrets User") rather than vault-level access policies.
    // This integrates with the same RBAC system used everywhere in Azure.
    enableRbacAuthorization: true

    // Soft delete: Deleted secrets are retained for 7 days (minimum allowed).
    // This protects against accidental deletion.
    enableSoftDelete: true
    softDeleteRetentionInDays: 7

    // Purge protection: In dev, we DISABLE this so we can fully delete and
    // recreate the vault during development. In prod, enable it to prevent
    // permanent deletion (even by admins) for the retention period.
    enablePurgeProtection: environment == 'prod' ? true : null
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
@description('The name of the Key Vault')
output vaultName string = keyVault.name

@description('The URI of the Key Vault (used in secret references)')
output vaultUri string = keyVault.properties.vaultUri
