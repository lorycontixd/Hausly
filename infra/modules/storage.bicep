// ============================================================================
// AZURE BLOB STORAGE — infra/modules/storage.bicep
// ============================================================================
// WHAT IS THIS?
// Azure Blob Storage is object storage — it stores files (blobs) of any type
// and size. Think of it like an infinite hard drive in the cloud.
//
// WHY DO WE NEED IT?
// Hausly stores:
// - Receipt photos (expense OCR)
// - Profile pictures
// - Pinboard photo attachments
// - Recipe images (v3)
//
// HOW DOES IT WORK?
// - A "Storage Account" is the top-level resource (like a server)
// - Inside it, you create "Containers" (like folders — NOT Docker containers!)
// - Inside containers, you store "Blobs" (the actual files)
//
// Example structure:
//   st-hausly-dev (storage account)
//   ├── receipts/ (container)
//   │   ├── household-123/receipt-456.jpg
//   │   └── household-123/receipt-789.png
//   ├── profiles/ (container)
//   │   └── user-abc/avatar.jpg
//   └── pinboard/ (container)
//       └── household-123/photo-001.jpg
//
// ACCESS PATTERNS:
// - Upload: Mobile app gets a SAS (Shared Access Signature) URL from backend,
//   then uploads directly to Blob Storage. Backend never handles the file bytes.
// - Download: Backend generates a read-only SAS URL with expiry, returns it to client.
//
// REDUNDANCY OPTIONS:
// - LRS (Locally Redundant): 3 copies in one datacenter. Cheapest. Good for dev.
// - GRS (Geo-Redundant): 6 copies across 2 regions. Survives regional disasters.
//   Required for production data you can't recreate.
//
// DEV vs PROD:
// - Dev: Standard_LRS (local redundancy only). Cheapest possible. Cents/month.
// - Prod: Standard_GRS (geo-redundant). User photos are irreplaceable data.
// ============================================================================

@description('Deployment environment')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region')
param location string

// ─── TIER SELECTION ─────────────────────────────────────────────────────────
// Storage accounts have 2 dimensions:
// - Performance: Standard (HDD-backed) vs Premium (SSD-backed)
//   We use Standard — photos don't need SSD speeds.
// - Redundancy: LRS, ZRS, GRS, GZRS, RA-GRS, RA-GZRS
//   We use LRS for dev (cheapest) and GRS for prod (geo-redundant).

var skuName = environment == 'dev' ? 'Standard_LRS' : 'Standard_GRS'

// Storage account names must be globally unique, 3-24 chars, lowercase + numbers only.
// No hyphens allowed! That's why naming is different from other resources.
var storageAccountName = 'sthausly${environment}'

// ─── RESOURCE: Storage Account ──────────────────────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: skuName
  }
  kind: 'StorageV2' // General-purpose v2: supports blobs, files, queues, tables

  properties: {
    // Access tier: Hot vs Cool vs Archive
    // Hot: Frequent access, higher storage cost, lower access cost
    // Cool: Infrequent access (30+ days), lower storage, higher access cost
    // We use Hot because receipts/photos are accessed frequently after upload.
    accessTier: 'Hot'

    // HTTPS only: Reject any unencrypted HTTP requests.
    // All data in transit is encrypted via TLS.
    supportsHttpsTrafficOnly: true

    // Minimum TLS version for security compliance
    minimumTlsVersion: 'TLS1_2'

    // Allow shared key access: SAS tokens use this.
    // SAS = Shared Access Signature = temporary, scoped access URLs.
    allowSharedKeyAccess: true

    // Blob public access: DISABLED. No anonymous access to any blob.
    // All access requires authentication (SAS token or Azure AD).
    allowBlobPublicAccess: false
  }
}

// ─── RESOURCE: Blob Service (required parent for containers) ────────────────
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    // Soft delete: Deleted blobs are recoverable for N days.
    // Protects against accidental deletion of user photos.
    deleteRetentionPolicy: {
      enabled: true
      days: environment == 'dev' ? 7 : 30
    }
  }
}

// ─── RESOURCE: Containers (the "folders" for our blobs) ─────────────────────
// privateAccess = no anonymous read. All access requires SAS or Azure AD.

resource receiptsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'receipts'
  properties: {
    publicAccess: 'None'
  }
}

resource profilesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'profiles'
  properties: {
    publicAccess: 'None'
  }
}

resource pinboardContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'pinboard'
  properties: {
    publicAccess: 'None'
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
@description('Storage account name (used for connection strings)')
output accountName string = storageAccount.name

@description('Primary blob endpoint URL')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

