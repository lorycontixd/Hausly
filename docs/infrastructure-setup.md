# Hausly Cloud Infrastructure Setup Guide

- Read: false
- Approved: false
- Notes: NA

---

## Overview

Hausly uses a hybrid cloud setup:
- **Firebase** (Google): Authentication only
- **Azure**: Everything else (compute, database, storage, real-time, AI)

There are **two environments**, each in its own Azure Resource Group:
| Environment | Resource Group | Purpose | Cost Target |
|-------------|---------------|---------|-------------|
| Dev | `hausly-dev-rg` | Development & testing | Cheapest possible (~€5-15/month) |
| Prod | `hausly-prod-rg` | Production deployment | Scalable & available (~€34-49/month) |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FIREBASE (Google Cloud)                        │
│  ┌─────────────────┐                                                 │
│  │  Firebase Auth   │  ← Mobile app authenticates here               │
│  │  (Free tier)     │  → Returns JWT ID tokens                       │
│  └────────┬────────┘                                                 │
└───────────┼─────────────────────────────────────────────────────────┘
            │ ID Token (JWT)
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          AZURE (Resource Group)                       │
│                                                                       │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐    │
│  │ Container    │    │  PostgreSQL      │    │  Azure SignalR    │    │
│  │ Apps         │───▶│  Flexible Server │    │  Service          │    │
│  │ (FastAPI)    │    │                  │    │  (Serverless)     │    │
│  └──────┬───────┘    └─────────────────┘    └────────┬─────────┘    │
│         │                                             │              │
│         │    ┌─────────────────┐                      │              │
│         ├───▶│  Blob Storage   │                      │              │
│         │    └─────────────────┘                      │              │
│         │                                             │              │
│         │    ┌─────────────────┐                      │              │
│         ├───▶│  Azure OpenAI   │                      │              │
│         │    └─────────────────┘                      │              │
│         │                                             │              │
│         │    ┌─────────────────┐                      │              │
│         └───▶│  Key Vault      │                      │              │
│              └─────────────────┘                      │              │
│                                                       │              │
│              ┌─────────────────┐                      │              │
│              │  Log Analytics  │◀─────────────────────┘              │
│              └─────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

Before starting, you need:

1. **Azure CLI** installed: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
2. **Azure subscription** with at least €50/month credits (Avanade)
3. **Firebase project** created at https://console.firebase.google.com
4. **Bicep CLI** (comes with Azure CLI v2.20+)

Verify your tools:
```powershell
az --version          # Should be 2.50+
az bicep version      # Should be 0.20+
```

---

## Step 1: Firebase Setup (Manual — One Time)

Firebase Auth is NOT deployed via Bicep — it's a Google service configured through the Firebase Console.

### 1.1 Create Firebase Project
1. Go to https://console.firebase.google.com
2. Click "Add Project" → Name it `hausly-dev` (or `hausly-prod`)
3. Disable Google Analytics (not needed)
4. Wait for project creation

### 1.2 Enable Authentication Providers
1. In Firebase Console → Authentication → Sign-in method
2. Enable:
   - **Email/Password** (for dev/testing)
   - **Google** (primary social login)
   - **Apple** (required for iOS App Store)

### 1.3 Generate Service Account Key
1. Firebase Console → Project Settings → Service Accounts
2. Click "Generate New Private Key"
3. Save as `firebase-sa.json` in `apps/api/`
4. **NEVER commit this file** — it's in `.gitignore`

### 1.4 Configure for Mobile App
1. Firebase Console → Project Settings → General
2. Add an iOS app (bundle ID: `com.hausly.app`)
3. Add an Android app (package: `com.hausly.app`)
4. Download `google-services.json` (Android) and `GoogleService-Info.plist` (iOS)
5. Place them in `apps/mobile/android/app/` and `apps/mobile/ios/` respectively

### 1.5 Firebase Projects (Dev vs Prod)
Create **two separate Firebase projects**:
- `hausly-dev` — for development
- `hausly-prod` — for production

Each has its own service account key and configuration files.

---

## Step 2: Azure Login & Subscription Setup

```powershell
# Login to Azure
az login

# List subscriptions (find your Avanade one)
az account list --output table

# Set the active subscription
az account set --subscription "<your-subscription-id>"

# Verify
az account show --output table
```

---

## Step 3: Create Resource Groups

Resource Groups are logical containers for Azure resources. We use one per environment for isolation.

```powershell
# Dev resource group (West Europe for EU data residency)
az group create --name hausly-dev-rg --location westeurope

# Prod resource group (same region for consistency)
az group create --name hausly-prod-rg --location westeurope
```

**Why West Europe?** Closest Azure region to Italy/EU. Low latency for users, GDPR compliance.

---

## Step 4: Deploy Infrastructure with Bicep

### What is Bicep?
Bicep is Azure's Infrastructure-as-Code (IaC) language. It compiles to ARM templates but is much more readable. Think of it like Terraform but Azure-native.

### Deploy Dev Environment
```powershell
az deployment group create \
  --resource-group hausly-dev-rg \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam
```

### Deploy Prod Environment
```powershell
az deployment group create \
  --resource-group hausly-prod-rg \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam
```

---

## Step 5: Post-Deployment Configuration

### 5.1 Store Secrets in Key Vault
After deployment, manually store the secrets that can't be auto-generated:

```powershell
# Dev environment
az keyvault secret set --vault-name kv-hauslyapp-dev --name "FIREBASE-SA-JSON" --file apps/api/firebase-sa.json

# The DATABASE-URL and SIGNALR-CONNECTION-STRING are auto-generated during deployment
# and stored in Key Vault by the Bicep template.
```

### 5.2 Get Connection Strings for Local Development
```powershell
# Get SignalR connection string (to put in local .env)
az signalr key list --name signalr-hausly-dev --resource-group hausly-dev-rg --query primaryConnectionString -o tsv

# Get PostgreSQL connection string
# Format: postgresql+asyncpg://{admin}:{password}@{server}.postgres.database.azure.com:5432/hausly?sslmode=require
```

### 5.3 Deploy the Container Image
```powershell
# Build and push Docker image (after ACR exists)
az acr build --registry crhauslydev --image hausly-api:latest apps/api/

# Container App will auto-pull from ACR (configured in Bicep)
```

---

## Step 6: Azure OpenAI Setup (Manual — Requires Approval)

Azure OpenAI requires a separate approval process. It cannot be fully automated via Bicep on first setup.

### 6.1 Request Access
1. Go to https://aka.ms/oai/access
2. Fill the form with your Azure subscription ID
3. Wait for approval (usually 1-2 business days)

### 6.2 Create Resource (after approval)
```powershell
az cognitiveservices account create \
  --name oai-hausly-dev \
  --resource-group hausly-dev-rg \
  --kind OpenAI \
  --sku S0 \
  --location swedencentral \
  --custom-domain oai-hausly-dev
```

**Why Sweden Central?** Azure OpenAI has limited region availability. Sweden Central has GPT-4o-mini.

### 6.3 Deploy Model
```powershell
az cognitiveservices account deployment create \
  --name oai-hausly-dev \
  --resource-group hausly-dev-rg \
  --deployment-name gpt-4o-mini \
  --model-name gpt-4o-mini \
  --model-version "2024-07-18" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

### 6.4 Get Endpoint & Key
```powershell
az cognitiveservices account show --name oai-hausly-dev --resource-group hausly-dev-rg --query properties.endpoint -o tsv
az cognitiveservices account keys list --name oai-hausly-dev --resource-group hausly-dev-rg --query key1 -o tsv
```

Store these in Key Vault:
```powershell
az keyvault secret set --vault-name kv-hauslyapp-dev --name "AZURE-OPENAI-ENDPOINT" --value "<endpoint>"
az keyvault secret set --vault-name kv-hauslyapp-dev --name "AZURE-OPENAI-KEY" --value "<key>"
```

---

## Step 7: Verify Deployment

### Check all resources are created:
```powershell
az resource list --resource-group hausly-dev-rg --output table
```

### Test Container App is running:
```powershell
# Get the app URL
az containerapp show --name ca-hausly-dev --resource-group hausly-dev-rg --query properties.configuration.ingress.fqdn -o tsv

# Health check
curl https://<fqdn>/health
```

### Test SignalR is reachable:
```powershell
az signalr show --name signalr-hausly-dev --resource-group hausly-dev-rg --query hostName -o tsv
```

---

## Dev vs Prod Differences Summary

| Resource | Dev Tier | Prod Tier | Cost Difference |
|----------|----------|-----------|-----------------|
| SignalR | Free_F1 (20 conns) | Standard_S1 (1K conns) | €0 vs ~€13/month |
| PostgreSQL | Burstable B1ms (1 vCore, 2GB) | GeneralPurpose D2s_v3 (2 vCores, 8GB), HA | ~€15 vs ~€100/month |
| Container Apps | 0.25 CPU, 0.5Gi, 0 min replicas | 0.5 CPU, 1Gi, 1 min replica | ~€0-5 vs ~€15-30/month |
| Blob Storage | Standard_LRS (no redundancy) | Standard_GRS (geo-redundant) | cents vs cents |
| Key Vault | Standard | Standard | ~€0.03/10K ops |
| Log Analytics | Free (500MB/day) | PerGB2018 | €0 vs ~€2-5/month |
| Container Registry | Basic | Standard | ~€5 vs ~€20/month |

---

## Troubleshooting

### "InsufficientQuota" error on PostgreSQL
The Burstable B1ms tier may not be available in all regions. Try `westeurope` or `northeurope`.

### Container App won't start
Check logs: `az containerapp logs show --name ca-hausly-dev --resource-group hausly-dev-rg`

### SignalR connection refused
Ensure the service is in **Serverless** mode (not Default or Classic).

### Key Vault access denied
The Container App's managed identity needs the `Key Vault Secrets User` role. This is assigned in the Bicep template.

---

## Cleanup

To tear down an environment completely:
```powershell
# WARNING: This deletes EVERYTHING in the resource group
az group delete --name hausly-dev-rg --yes --no-wait
```
