// ============================================================================
// AZURE SIGNALR SERVICE — infra/modules/signalr.bicep
// ============================================================================
// WHAT IS THIS?
// Azure SignalR Service is a managed WebSocket relay. It handles thousands of
// persistent WebSocket connections so your backend doesn't have to.
//
// WHY DO WE NEED IT?
// Real-time updates (grocery list changes, expense notifications, chore completions)
// require persistent connections between the mobile app and the server.
// Our FastAPI backend can't efficiently manage thousands of WebSocket connections.
// SignalR Service acts as a middleman:
//   Mobile App ←WebSocket→ SignalR Service ←REST API→ FastAPI Backend
//
// HOW "SERVERLESS" MODE WORKS:
// There are 3 modes:
// - Default: Backend hosts a SignalR hub (persistent connection to service). .NET only.
// - Classic: Legacy compatibility mode.
// - Serverless: Backend talks to the service via REST API only. NO persistent
//   connection from backend. This is what we use because there's no Python hub SDK.
//
// FLOW:
// 1. Mobile app calls our /api/signalr/negotiate endpoint
// 2. Backend generates a JWT token with the user's groups (household:{id})
// 3. Mobile app connects directly to SignalR Service using that token
// 4. When something changes (e.g., expense created), backend POSTs to SignalR REST API
// 5. SignalR Service pushes the message to all connected clients in that group
//
// DEV vs PROD:
// - Dev: Free_F1 (20 concurrent connections, 20K messages/day)
//   → Plenty for solo development. €0/month.
// - Prod: Standard_S1 (1000 concurrent connections, unlimited messages, 1 unit)
//   → Can handle ~1000 simultaneous mobile users. ~€13/month per unit.
//   → Scales by adding units (each adds 1000 connections).
// ============================================================================

@description('Deployment environment')
@allowed(['dev', 'prod'])
param environment string

@description('Azure region')
param location string

// ─── TIER SELECTION ─────────────────────────────────────────────────────────
// Free_F1: 20 connections, 20K messages/day, 0 units. Perfect for dev.
// Standard_S1: 1000 connections per unit, unlimited messages. Production-grade.
//
// 'capacity' (units) only applies to Standard tier. Each unit = 1000 connections.
// Free tier doesn't support units (always 1, set to 1 for schema compliance).

var skuName = environment == 'dev' ? 'Free_F1' : 'Standard_S1'
var capacity = environment == 'dev' ? 1 : 1

// ─── RESOURCE DEFINITION ────────────────────────────────────────────────────
resource signalrService 'Microsoft.SignalRService/signalR@2024-03-01' = {
  name: 'signalr-hausly-${environment}'
  location: location
  sku: {
    name: skuName
    capacity: capacity
  }
  kind: 'SignalR'
  properties: {
    features: [
      {
        // ServiceMode: Controls how the backend interacts with SignalR.
        // 'Serverless' = backend uses REST API only (no persistent hub connection)
        // This is the ONLY option that works with non-.NET backends.
        flag: 'ServiceMode'
        value: 'Serverless'
      }
      {
        // EnableConnectivityLogs: Logs connection/disconnection events.
        // Useful for debugging "why isn't my client receiving messages?"
        flag: 'EnableConnectivityLogs'
        value: 'true'
      }
      {
        // EnableMessagingLogs: Logs message send/receive events.
        // WARNING: Can be verbose in production. Enable selectively.
        flag: 'EnableMessagingLogs'
        value: environment == 'dev' ? 'true' : 'false'
      }
    ]

    // CORS: Which origins can establish WebSocket connections to the service.
    // The mobile app connects directly to SignalR (not through our backend),
    // so we need to allow the Expo dev server and the production app.
    cors: {
      allowedOrigins: environment == 'dev' ? [
        'http://localhost:8081'   // Expo dev server
        'http://localhost:19006'  // Expo web
        '*'                       // Dev convenience — allow all
      ] : [
        'https://hausly.app'     // Production domain
      ]
    }

    // TLS: Minimum TLS version for connections. 1.2 is the security standard.
    tls: {
      clientCertEnabled: false
    }
  }
}

// ─── OUTPUTS ────────────────────────────────────────────────────────────────
@description('SignalR service hostname (for client connections)')
output hostname string = signalrService.properties.hostName

@description('SignalR resource ID')
output resourceId string = signalrService.id

