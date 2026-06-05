# Real-Time Architecture — Azure SignalR (Serverless Mode)

> Describes how Hausly uses Azure SignalR Service in serverless mode to push real-time events from the backend to mobile clients.
- Read: false
- Approved: false
- Notes: NA

---

## Overview

Hausly uses **Azure SignalR Service in Serverless mode** as a managed WebSocket relay. The backend does not host a SignalR hub — it sends messages to the service via REST API, and the service relays them to connected clients over WebSocket.

Clients never open WebSocket connections to the FastAPI backend. They connect directly to Azure SignalR Service after receiving a token from the backend's negotiate endpoint.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     AZURE SIGNALR SERVICE                         │
│  Mode: Serverless                                                │
│  Hub: "household"                                                │
│  Groups: household:{uuid-1}, household:{uuid-2}, ...             │
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │ Connection A │    │ Connection B │    │ Connection C │          │
│  │ (Lorenzo)   │    │ (Maria)     │    │ (Paolo)     │          │
│  │ group: h:1  │    │ group: h:1  │    │ group: h:1  │          │
│  └──────▲──────┘    └──────▲──────┘    └──────▲──────┘          │
│         │ WebSocket         │                   │                  │
└─────────┼───────────────────┼───────────────────┼─────────────────┘
          │                   │                   │
          │         ┌─────────┼───────────────────┘
          │         │         │
┌─────────┴─────────┴─────────┴──────────────────────────────────┐
│                    MOBILE CLIENTS                                │
│  1. On app launch: POST /hubs/household/negotiate               │
│  2. Receive: { url, accessToken }                               │
│  3. Connect WebSocket to Azure SignalR Service directly          │
│  4. Listen for events (grocery:item_added, expense:created...)  │
└─────────────────────────────────────────────────────────────────┘
          │
          │ REST API calls (mutations)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                               │
│                                                                  │
│  1. Receives mutation (e.g. POST /grocery/items)                │
│  2. Writes to DB                                                │
│  3. Calls Azure SignalR REST API to broadcast to group          │
│     POST https://{signalr-host}/api/hubs/household/             │
│          groups/household:{household_id}                         │
│     Body: { target: "event_name", arguments: [payload] }        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why Serverless Mode

Azure SignalR has three modes: Default, Classic, and Serverless.

- **Default** mode requires the backend to host a SignalR hub (a persistent connection between backend and service). This is the .NET ASP.NET Core pattern — not available in Python.
- **Serverless** mode treats the service as a pure relay. The backend only interacts via REST API. No persistent connection from the server. This is the correct mode for FastAPI.

There is no Python-native SignalR server SDK. The Azure Functions bindings shown in Microsoft docs are syntactic sugar over the same REST API we call directly.

---

## Connection Flow

### Step 1: Client Calls Negotiate

The `@microsoft/signalr` client library has a built-in negotiate step. When you point it at a hub URL, it automatically appends `/negotiate` and makes a POST request.

Client configures: `hubUrl = "{API_BASE_URL}/hubs/household"`
Client automatically calls: `POST {API_BASE_URL}/hubs/household/negotiate`

The Firebase auth token is sent in the Authorization header of this HTTP request (same as any other API call).

### Step 2: Backend Generates Client Token

The negotiate endpoint:
1. Authenticates the user via Firebase token (standard auth dependency)
2. Looks up the user's active household membership
3. Generates a short-lived JWT signed with the SignalR access key
4. Returns `{ url, accessToken }` to the client

The JWT contains:
- `aud` (audience): the SignalR client URL — `https://{endpoint}/client/?hub=household`
- `sub` (subject): the user's ID — used as the connection's identity in SignalR
- `exp` (expiry): 1 hour from now
- `asrs.s.gp` (group claim): `household:{household_id}` — tells SignalR to auto-add this connection to the group on connect

### Step 3: Client Connects to Azure SignalR Service

The client library receives the negotiate response and opens a WebSocket directly to Azure SignalR Service (not to our backend). The `accessToken` is used as auth for this WebSocket.

From this point, the client is listening for server-sent events. It does not send mutations through the WebSocket — all mutations go via REST.

### Step 4: Backend Broadcasts After Mutations

When a mutation occurs (item added, expense confirmed, chore completed, etc.):
1. The service layer writes to the database
2. After successful commit, it calls the Azure SignalR REST API
3. The REST call targets a specific group (the household)
4. Azure SignalR relays the message to all WebSocket connections in that group

---

## Key Concepts

### Hub

A logical namespace for connections. Hausly uses a single hub named `household`. All connections join this hub; isolation between households is achieved via groups.

### Groups

A group is a named subset of connections within a hub. Hausly names groups `household:{household_id}`. All members of a household are in the same group.

A user is assigned to their group automatically on connect via the `asrs.s.gp` JWT claim in the negotiate token. No separate "join group" REST call is needed for v1 (single-household constraint means one group per user).

### Events (target + arguments)

Messages sent through SignalR have a `target` (event name string) and `arguments` (array of payloads). The client registers listeners by target name.

Example: `{ "target": "grocery:item_added", "arguments": [{ "id": "...", "name": "Milk", ... }] }`

See `docs/api-reference.md` § Real-Time for the full event catalogue.

### SignalR Channel is Read-Only for Clients

Clients receive events but never send messages through the WebSocket. All mutations go through REST endpoints. This keeps the mutation path auditable, prevents dual-write issues, and simplifies error handling.

---

## Connection String

The Azure SignalR connection string has this structure:
```
Endpoint=https://hausly-dev.service.signalr.net;AccessKey=<base64-key>;Version=1.0;
```

Parsed into two pieces:
- **Endpoint**: the service URL (used for both client connections and REST API calls)
- **AccessKey**: a symmetric key used to sign JWTs (for both client tokens and server-to-service auth)

Stored in: `SIGNALR_CONNECTION_STRING` environment variable.

---

## REST API (Backend → SignalR Service)

The backend uses the Azure SignalR data-plane REST API to send messages.

### Send to Group

```
POST https://{endpoint}/api/hubs/{hub}/groups/{group}
Authorization: Bearer {server-jwt}
Content-Type: application/json

{
  "target": "event_name",
  "arguments": [{ ...payload }]
}
```

The server JWT is signed with the same access key, with `aud` set to the request URL.

### Other Available Operations (not needed for v1)

- Send to a specific user: `POST /api/hubs/{hub}/users/{userId}`
- Send to all connections: `POST /api/hubs/{hub}`
- Add/remove connection from group: `PUT/DELETE /api/hubs/{hub}/groups/{group}/connections/{connectionId}`

---

## Token Signing

Both the negotiate client token and the server-to-service auth token are JWTs signed with HS256 using the AccessKey from the connection string.

**Client token** (returned by negotiate):
- `aud`: `https://{endpoint}/client/?hub=household`
- `sub`: user ID
- `exp`: 1 hour
- `asrs.s.gp`: group name (auto-join)

**Server token** (used in REST API calls):
- `aud`: the full URL being called
- `exp`: 5 minutes (short-lived, generated per request)

Libraries used: `python-jose` for JWT encoding (already in dependencies).

---

## Failure Handling

SignalR broadcast is **fire-and-forget**. If the SignalR service is unavailable:
- The mutation still succeeds (DB write is the source of truth)
- The broadcast failure is logged as a warning
- Clients will pick up the state on next query/refresh
- The request must never fail because SignalR is down

---

## Multi-Household (Future)

In v1, users belong to one household, so the negotiate token contains a single group claim. If multi-household support is added later, the negotiate endpoint would either:
- Include multiple `asrs.s.gp` claims (one per household), or
- Use the REST API to add the connection to multiple groups after connect

This is a future concern — the architecture supports it without structural changes.

---

## Technology Choices Summary

| Concern | Decision | Rationale |
|---------|----------|-----------|
| SignalR mode | Serverless | No Python hub SDK exists; REST API works from any language |
| Python SDK | None — use `httpx` + `python-jose` | Both already in deps; no dedicated Python SignalR server package exists |
| Token generation | Manual JWT with `python-jose` | Standard HS256 signing; avoids unnecessary dependencies |
| HTTP client for REST API | `httpx` (async) | Already a project dependency; async-native |
| Client library | `@microsoft/signalr` npm package | Official client; handles negotiate, reconnection, transport fallback |
| Hub name | `household` | Single hub; group-level isolation is sufficient |
| Group naming | `household:{household_id}` | Unique per household; human-readable in logs |
| Group assignment | JWT claim (`asrs.s.gp`) at negotiate time | Simpler than post-connect REST call; sufficient for single-household v1 |
| Failure mode | Fire-and-forget with warning log | Mutations must not fail due to real-time broadcast issues |

---

## Why "Negotiate"?

The name is part of the SignalR protocol standard. The `@microsoft/signalr` client library hardcodes a `POST /negotiate` call as the first step of any connection. Originally, it let client and server "negotiate" the transport (WebSocket vs SSE vs Long Polling). In serverless mode, it redirects the client to the Azure SignalR Service URL with an access token. The endpoint path cannot be renamed — the client library expects it.
