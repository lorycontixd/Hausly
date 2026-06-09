# =============================================================================
# Phase 7 — Real-Time (SignalR) Manual Test Script
# =============================================================================
# Assumes:
#   - Server running: cd apps/api && uvicorn hausly.main:app --reload
#   - PostgreSQL running with migrations applied (alembic upgrade head)
#   - Two Firebase test users exist with valid tokens
#   - SIGNALR_CONNECTION_STRING set in .env (or empty for degradation test)
#
# Tests:
#   1. Negotiate endpoint returns connection info (200)
#   2. Negotiate requires authentication (401 without token)
#   3. Negotiate fails gracefully when user has no household (400)
#   4. Grocery mutation triggers broadcast (verified via server logs)
#   5. Expense mutation triggers broadcast
#   6. Meal mutation triggers broadcast
#   7. Chore mutation triggers broadcast
#   8. Fire-and-forget: mutations succeed even without SignalR configured
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Configuration ---
$first_user_token = "<first-user-token>"
$second_user_token = "<second-user-token>"
$HEADERS = @{ "Authorization" = "Bearer $first_user_token"; "Content-Type" = "application/json" }
$HEADERS2 = @{ "Authorization" = "Bearer $second_user_token"; "Content-Type" = "application/json" }
$BASE = "http://localhost:8000/api/v1"

# =============================================================================
# Setup: Verify users and get/create household
# =============================================================================
Write-Host "=== Setup: Verifying users and household ==="

# Verify user 1 (admin)
$user1 = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS
$USER1_ID = $user1.user_id
Write-Host "User 1 (admin): $($user1.display_name) ($USER1_ID)"

# Verify user 2 (member)
$user2 = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS2
$USER2_ID = $user2.user_id
Write-Host "User 2 (member): $($user2.display_name) ($USER2_ID)"

# Get or create household
if ($user1.households -and $user1.households.Count -gt 0) {
    $HID = $user1.households[0].id
    Write-Host "Using existing household: $HID"
} else {
    Write-Host "Creating new household..."
    $household = Invoke-RestMethod -Uri "$BASE/households" `
        -Method POST -Headers $HEADERS `
        -Body '{"name": "SignalR Test Home", "type": "couple"}'
    $HID = $household.id
    Write-Host "Created household: $HID (invite code: $($household.invite_code))"

    # User 2 joins
    $user2_check = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS2
    if (-not $user2_check.households -or $user2_check.households.Count -eq 0) {
        $joinBody = @{ invite_code = $household.invite_code } | ConvertTo-Json
        Invoke-RestMethod -Uri "$BASE/households/join" -Method POST -Headers $HEADERS2 -Body $joinBody | Out-Null
        Write-Host "User 2 joined household."
    }
}

Write-Host "=== Setup complete ==="
Write-Host ""

# =============================================================================
# Test 1: Negotiate endpoint returns connection info (200)
# =============================================================================
Write-Host "=== Test 1: Negotiate endpoint (happy path) ==="
Write-Host "  Expected: 200 with { url, accessToken } OR 503 if SignalR not configured"

try {
    $negotiate = Invoke-RestMethod -Uri "$BASE/hubs/household/negotiate" `
        -Method POST -Headers $HEADERS

    Write-Host "  url: $($negotiate.url)"
    Write-Host "  accessToken: $($negotiate.accessToken.Substring(0, [Math]::Min(50, $negotiate.accessToken.Length)))..."

    if ($negotiate.url -and $negotiate.accessToken) {
        # Validate URL format
        if ($negotiate.url -match "client/\?hub=household") {
            Write-Host "  PASS: Negotiate returns valid connection info" -ForegroundColor Green
        } else {
            Write-Host "  FAIL: URL doesn't match expected format" -ForegroundColor Red
        }
    } else {
        Write-Host "  FAIL: Missing url or accessToken" -ForegroundColor Red
    }
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 503) {
        Write-Host "  Status: 503 (SignalR not configured — expected in dev without connection string)"
        Write-Host "  PASS (degradation): Service correctly reports unavailability" -ForegroundColor Yellow
    } else {
        Write-Host "  FAIL: Unexpected error $statusCode" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)"
    }
}
Write-Host ""

# =============================================================================
# Test 2: Negotiate requires authentication (401 without token)
# =============================================================================
Write-Host "=== Test 2: Negotiate without auth token ==="
Write-Host "  Expected: 401 Unauthorized"

try {
    $noAuthHeaders = @{ "Content-Type" = "application/json" }
    Invoke-RestMethod -Uri "$BASE/hubs/household/negotiate" `
        -Method POST -Headers $noAuthHeaders
    Write-Host "  FAIL: Should have returned 401" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"
    if ($statusCode -eq 401) {
        Write-Host "  PASS: Auth required for negotiate" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 401, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 3: Grocery mutation works (broadcast fires in background)
# =============================================================================
Write-Host "=== Test 3: Grocery mutation triggers broadcast ==="
Write-Host "  Expected: 201 (mutation succeeds; check server logs for broadcast)"
Write-Host "  NOTE: If SignalR is configured, server logs will show broadcast attempt"
Write-Host "        If not configured, broadcast is silently skipped (fire-and-forget)"

$itemBody = '[{"name":"SignalR Test Milk","quantity":1,"unit":"L"}]'

try {
    $items = Invoke-RestMethod -Uri "$BASE/households/$HID/grocery/items" `
        -Method POST -Headers $HEADERS -Body $itemBody
    $ITEM_ID = $items[0].id
    Write-Host "  Created item: $ITEM_ID ($($items[0].name))"
    Write-Host "  PASS: Mutation succeeded (broadcast fire-and-forget)" -ForegroundColor Green
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  FAIL: Mutation failed with $statusCode" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)"
}
Write-Host ""

# =============================================================================
# Test 4: Grocery update triggers broadcast
# =============================================================================
Write-Host "=== Test 4: Grocery update triggers broadcast ==="
Write-Host "  Expected: 200 (update succeeds)"

if ($ITEM_ID) {
    $updateBody = @{ name = "SignalR Test Oat Milk" } | ConvertTo-Json
    try {
        $updated = Invoke-RestMethod -Uri "$BASE/households/$HID/grocery/items/$ITEM_ID" `
            -Method PATCH -Headers $HEADERS -Body $updateBody
        Write-Host "  Updated item: $($updated.name)"
        Write-Host "  PASS: Update succeeded (broadcast fire-and-forget)" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL: Update failed" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No item to update" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 5: Grocery delete triggers broadcast
# =============================================================================
Write-Host "=== Test 5: Grocery delete triggers broadcast ==="
Write-Host "  Expected: 204 (delete succeeds)"

if ($ITEM_ID) {
    try {
        Invoke-RestMethod -Uri "$BASE/households/$HID/grocery/items/$ITEM_ID" `
            -Method DELETE -Headers $HEADERS
        Write-Host "  Deleted item: $ITEM_ID"
        Write-Host "  PASS: Delete succeeded (broadcast fire-and-forget)" -ForegroundColor Green
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "  FAIL: Delete failed with $statusCode" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No item to delete" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 6: Expense create triggers broadcast
# =============================================================================
Write-Host "=== Test 6: Expense create triggers broadcast ==="
Write-Host "  Expected: 201 (expense created)"

$expenseBody = @{
    title = "SignalR Test Expense"
    amount = 20.00
    currency = "EUR"
    paid_by_user_id = $USER1_ID
    splits = @(
        @{ user_id = $USER1_ID; share_amount = 10.00 }
        @{ user_id = $USER2_ID; share_amount = 10.00 }
    )
    status = "draft"
} | ConvertTo-Json -Depth 3

try {
    $expense = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
        -Method POST -Headers $HEADERS -Body $expenseBody
    $EXPENSE_ID = $expense.id
    Write-Host "  Created expense: $EXPENSE_ID ($($expense.title))"
    Write-Host "  PASS: Expense creation succeeded (broadcast fire-and-forget)" -ForegroundColor Green
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  FAIL: Expense creation failed with $statusCode" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)"
}
Write-Host ""

# =============================================================================
# Test 7: Expense confirm triggers broadcast
# =============================================================================
Write-Host "=== Test 7: Expense confirm triggers broadcast ==="
Write-Host "  Expected: 200 (expense confirmed)"

if ($EXPENSE_ID) {
    try {
        $confirmed = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE_ID/confirm" `
            -Method POST -Headers $HEADERS
        Write-Host "  Confirmed expense: $($confirmed.status)"
        Write-Host "  PASS: Confirm succeeded (broadcast fire-and-forget)" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL: Confirm failed" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No expense to confirm" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 8: Meal create triggers broadcast
# =============================================================================
Write-Host "=== Test 8: Meal create triggers broadcast ==="
Write-Host "  Expected: 201 (meal entry created)"

$TODAY = (Get-Date).ToString("yyyy-MM-dd")
$mealBody = @{
    date = $TODAY
    slot = "dinner"
    text = "SignalR Test Pasta"
    headcount = 2
} | ConvertTo-Json

try {
    $meal = Invoke-RestMethod -Uri "$BASE/households/$HID/meals" `
        -Method POST -Headers $HEADERS -Body $mealBody
    $MEAL_ID = $meal.id
    Write-Host "  Created meal entry: $MEAL_ID ($($meal.text))"
    Write-Host "  PASS: Meal creation succeeded (broadcast fire-and-forget)" -ForegroundColor Green
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 409) {
        Write-Host "  Slot already taken (409) — expected if re-running tests"
        Write-Host "  PASS (idempotent): Meal slot conflict handled correctly" -ForegroundColor Yellow
    } else {
        Write-Host "  FAIL: Meal creation failed with $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 9: Meal delete triggers broadcast
# =============================================================================
Write-Host "=== Test 9: Meal delete triggers broadcast ==="
Write-Host "  Expected: 204 (meal entry deleted)"

if ($MEAL_ID) {
    try {
        Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$MEAL_ID" `
            -Method DELETE -Headers $HEADERS
        Write-Host "  Deleted meal entry: $MEAL_ID"
        Write-Host "  PASS: Meal delete succeeded (broadcast fire-and-forget)" -ForegroundColor Green
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "  FAIL: Meal delete failed with $statusCode" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No meal entry to delete" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 10: Chore create triggers broadcast
# =============================================================================
Write-Host "=== Test 10: Chore create triggers broadcast ==="
Write-Host "  Expected: 201 (chore created)"

$choreBody = @{
    name = "SignalR Test Chore"
    start_date = $TODAY
    is_recurring = $false
    assignee_user_ids = @($USER1_ID, $USER2_ID)
    rotation_enabled = $false
} | ConvertTo-Json

try {
    $chore = Invoke-RestMethod -Uri "$BASE/households/$HID/chores" `
        -Method POST -Headers $HEADERS -Body $choreBody
    $CHORE_ID = $chore.id
    Write-Host "  Created chore: $CHORE_ID ($($chore.name))"
    Write-Host "  PASS: Chore creation succeeded (broadcast fire-and-forget)" -ForegroundColor Green
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  FAIL: Chore creation failed with $statusCode" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)"
}
Write-Host ""

# =============================================================================
# Test 11: Chore assignment complete triggers broadcast
# =============================================================================
Write-Host "=== Test 11: Chore assignment complete triggers broadcast ==="
Write-Host "  Expected: 200 (assignment completed)"

if ($CHORE_ID) {
    # Get assignments for this chore
    $assignments = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?status=pending" `
        -Method GET -Headers $HEADERS
    $choreAssignments = $assignments | Where-Object { $_.chore_id -eq $CHORE_ID }
    $firstAssignment = $choreAssignments | Select-Object -First 1

    if ($firstAssignment) {
        try {
            $completed = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments/$($firstAssignment.id)/complete" `
                -Method POST -Headers $HEADERS
            Write-Host "  Completed assignment: $($completed.id) (status=$($completed.status))"
            Write-Host "  PASS: Complete succeeded (broadcast fire-and-forget)" -ForegroundColor Green
        } catch {
            Write-Host "  FAIL: Complete failed" -ForegroundColor Red
        }
    } else {
        Write-Host "  SKIP: No pending assignment found" -ForegroundColor Yellow
    }
} else {
    Write-Host "  SKIP: No chore created" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 12: Chore delete triggers broadcast
# =============================================================================
Write-Host "=== Test 12: Chore delete triggers broadcast ==="
Write-Host "  Expected: 204 (chore deleted)"

if ($CHORE_ID) {
    try {
        Invoke-RestMethod -Uri "$BASE/households/$HID/chores/$CHORE_ID" `
            -Method DELETE -Headers $HEADERS
        Write-Host "  Deleted chore: $CHORE_ID"
        Write-Host "  PASS: Chore delete succeeded (broadcast fire-and-forget)" -ForegroundColor Green
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "  FAIL: Chore delete failed with $statusCode" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No chore to delete" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Cleanup
# =============================================================================
Write-Host "=== Cleanup ==="

# Delete the test expense
if ($EXPENSE_ID) {
    try {
        Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE_ID" `
            -Method DELETE -Headers $HEADERS | Out-Null
        Write-Host "  Deleted test expense: $EXPENSE_ID"
    } catch {
        Write-Host "  (expense already deleted or confirmed — cannot delete confirmed expenses)"
    }
}

Write-Host "=== Cleanup complete ==="
Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "============================================================="
Write-Host "Phase 7 Manual Test Summary"
Write-Host "============================================================="
Write-Host ""
Write-Host "Key validation points:"
Write-Host "  1. Negotiate endpoint returns { url, accessToken } when configured"
Write-Host "  2. Negotiate requires authentication (401 without token)"
Write-Host "  3. All mutations succeed regardless of SignalR availability"
Write-Host "  4. Broadcast calls are fire-and-forget (check server logs for details)"
Write-Host ""
Write-Host "To verify broadcasts are actually sent, run the server with:"
Write-Host "  SIGNALR_CONNECTION_STRING=<your-connection-string> uvicorn hausly.main:app --reload --log-level debug"
Write-Host ""
Write-Host "Look for log lines like:"
Write-Host "  WARNING: SignalR broadcast failed: grocery:item_added household:... -> 401"
Write-Host "  (401 means token/endpoint mismatch — but confirms the broadcast was attempted)"
Write-Host ""
Write-Host "============================================================="
