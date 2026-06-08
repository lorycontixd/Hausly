$ErrorActionPreference = "Stop"

$first_user_token = "<first-user-token>"
$second_user_token = "<second-user-token>"
$HEADERS = @{ "Authorization" = "Bearer $first_user_token"; "Content-Type" = "application/json" }
$HEADERS2 = @{ "Authorization" = "Bearer $second_user_token"; "Content-Type" = "application/json" }

# --- Cleanup: remove users from any existing households ---
Write-Host "=== Cleanup: checking existing memberships ==="

# Remove user 2 first (non-admin), then user 1 (admin can leave when alone)
$user2 = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/verify" -Method POST -Headers $HEADERS2
if ($user2.households -and $user2.households.Count -gt 0) {
    foreach ($h in $user2.households) {
        Write-Host "User 2 leaving household $($h.id)..."
        try {
            Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$($h.id)/leave" -Method POST -Headers $HEADERS2 | Out-Null
            Write-Host "  Done."
        } catch {
            Write-Host "  (leave failed: $($_.Exception.Message))"
        }
    }
}

$user1 = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/verify" -Method POST -Headers $HEADERS
if ($user1.households -and $user1.households.Count -gt 0) {
    foreach ($h in $user1.households) {
        Write-Host "User 1 leaving household $($h.id)..."
        try {
            Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$($h.id)/leave" -Method POST -Headers $HEADERS | Out-Null
            Write-Host "  Done."
        } catch {
            Write-Host "  (leave failed: $($_.Exception.Message))"
        }
    }
}

Write-Host "=== Cleanup complete ==="
Write-Host ""

# --- Test begins ---

$resp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households" `
  -Method POST -Headers $HEADERS `
  -Body '{"name": "Test Home", "type": "couple"}'
$HID = $resp.id
$INVITE_CODE = $resp.invite_code
Write-Host "Household ID: $HID"
Write-Host "Invite Code: $INVITE_CODE"

# User 2 joins the household
Write-Host "`nUser 2 joining household..."
$joinBody = @{ invite_code = $INVITE_CODE } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/join" `
  -Method POST -Headers $HEADERS2 -Body $joinBody | Out-Null
Write-Host "User 2 joined successfully."

Write-Host "\nAdding grocery items..."
$resp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/items" `
  -Method POST -Headers $HEADERS `
  -Body '[{"name":"Milk","quantity":2,"unit":"L"},{"name":"Eggs","quantity":12},{"name":"Toothbrush","is_personal":true,"personal_visibility":"hidden"}]'
$resp | ConvertTo-Json
# Expected: 201, 3 items returned
$MILK_ID = $resp[0].id
$EGGS_ID = $resp[1].id
$BRUSH_ID = $resp[2].id
Write-Host "Milk ID: $MILK_ID, Eggs ID: $EGGS_ID, Toothbrush ID: $BRUSH_ID"

# Verify duplicate item name handling
Write-Host "\nAttempting to add duplicate item..."
try {
  Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/items" `
    -Method POST -Headers $HEADERS `
    -Body '[{"name":"milk"}]'
} catch {
  $_.Exception.Response.StatusCode  # Expected: 409
  $_ | ConvertFrom-Json              # Expected: DUPLICATE_ITEM
}

# Verify item retrieval - owner should see all items
Write-Host "\nRetrieving items as owner..."
$LIST_ID = (Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/lists" `
  -Method GET -Headers $HEADERS)[0].id

$items = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/lists/$LIST_ID/items" `
  -Method GET -Headers $HEADERS
$items.Count  # Expected: 3

# Use a second user's token who has joined the household
Write-Host "\nRetrieving items as second user..."

$items2 = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/lists/$LIST_ID/items" `
  -Method GET -Headers $HEADERS2
$items2.Count  # Expected: 2 (Toothbrush hidden)

# Verify item update
Write-Host "\nUpdating Milk item..."
$updated = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/items/$MILK_ID" `
  -Method PATCH -Headers $HEADERS `
  -Body '{"name":"Oat Milk","quantity":1}'
$updated.name  # Expected: "Oat Milk"

# Verify item deletion
Write-Host "\nDeleting Eggs item..."
$body = @{
  bought_item_ids = @($MILK_ID, $EGGS_ID, $BRUSH_ID)
  receipt_total = 25.50
  create_expense = $true
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/session/complete" `
  -Method POST -Headers $HEADERS -Body $body
$result | ConvertTo-Json -Depth 5

# Delete an item after adding new one (expect 204)
$new = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/items" `
  -Method POST -Headers $HEADERS -Body '[{"name":"Butter"}]'
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/items/$($new[0].id)" `
  -Method DELETE -Headers $HEADERS

# Archive the grocery list
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/households/$HID/grocery/lists/archive" `
  -Method POST -Headers $HEADERS -Body '{"confirm":true}'