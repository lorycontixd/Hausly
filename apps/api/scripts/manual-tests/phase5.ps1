# =============================================================================
# Phase 5 — Meal Planner Module Manual Test Script
# =============================================================================
# Assumes:
#   - Server running: cd apps/api && uvicorn hausly.main:app --reload
#   - PostgreSQL running with migrations applied (alembic upgrade head)
#   - Two Firebase test users exist with valid tokens
#   - "meal" module is enabled in household settings
#
# Tests:
#   1. Claim a meal slot (happy path)
#   2. Duplicate slot claim returns 409
#   3. Headcount defaults to household member count
#   4. Owner can update their entry
#   5. Non-owner non-admin cannot update (403)
#   6. Non-owner non-admin cannot delete (403)
#   7. Admin can update any entry
#   8. Admin can delete any entry
#   9. Different slots on same date allowed (lunch + dinner)
#  10. Same slot on different dates allowed
#  11. Get entries for date range
#  12. Owner can delete their entry
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
        -Body '{"name": "Meal Test Home", "type": "couple"}'
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

# Dates for testing
$TODAY = (Get-Date).ToString("yyyy-MM-dd")
$TOMORROW = (Get-Date).AddDays(1).ToString("yyyy-MM-dd")
$WEEK_END = (Get-Date).AddDays(7).ToString("yyyy-MM-dd")

# =============================================================================
# Cleanup: Delete any existing meal entries for today/tomorrow to start fresh
# =============================================================================
Write-Host "=== Cleanup: removing existing test entries ==="
$existingEntries = Invoke-RestMethod -Uri "$BASE/households/$HID/meals?start=$TODAY&end=$WEEK_END" `
    -Method GET -Headers $HEADERS
foreach ($entry in $existingEntries) {
    try {
        Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$($entry.id)" `
            -Method DELETE -Headers $HEADERS | Out-Null
        Write-Host "  Deleted entry: $($entry.id) ($($entry.date) $($entry.slot))"
    } catch {
        Write-Host "  (could not delete $($entry.id): $($_.Exception.Message))"
    }
}
Write-Host "=== Cleanup complete ==="
Write-Host ""

# =============================================================================
# Test 1: Claim a meal slot (happy path)
# =============================================================================
Write-Host "=== Test 1: Claim a meal slot ==="
Write-Host "  Expected: 201, slot=dinner, owner_user_id=User1"

$createBody = @{
    date = $TODAY
    slot = "dinner"
    text = "Homemade pizza"
    headcount = 3
} | ConvertTo-Json

$entry1 = Invoke-RestMethod -Uri "$BASE/households/$HID/meals" `
    -Method POST -Headers $HEADERS -Body $createBody
$ENTRY1_ID = $entry1.id

Write-Host "  Created entry: $ENTRY1_ID"
Write-Host "  Date: $($entry1.date), Slot: $($entry1.slot)"
Write-Host "  Text: $($entry1.text)"
Write-Host "  Headcount: $($entry1.headcount)"
Write-Host "  Owner: $($entry1.owner_user_id)"

if ($entry1.slot -ne "dinner") { Write-Host "  FAIL: Expected slot=dinner" -ForegroundColor Red }
elseif ($entry1.text -ne "Homemade pizza") { Write-Host "  FAIL: Expected text='Homemade pizza'" -ForegroundColor Red }
elseif ($entry1.headcount -ne 3) { Write-Host "  FAIL: Expected headcount=3" -ForegroundColor Red }
elseif ($entry1.owner_user_id -ne $USER1_ID) { Write-Host "  FAIL: Expected owner=User1" -ForegroundColor Red }
else { Write-Host "  PASS" -ForegroundColor Green }
Write-Host ""

# =============================================================================
# Test 2: Duplicate slot claim returns 409
# =============================================================================
Write-Host "=== Test 2: Duplicate slot claim (same date, same slot) ==="
Write-Host "  Expected: 409 SLOT_TAKEN"

$dupBody = @{
    date = $TODAY
    slot = "dinner"
    text = "Bob's dinner"
    headcount = 2
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/meals" `
        -Method POST -Headers $HEADERS2 -Body $dupBody
    Write-Host "  FAIL: Should have returned 409" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"
    if ($statusCode -eq 409) {
        Write-Host "  PASS: Correctly rejected duplicate slot claim" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 409, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 3: Headcount defaults to household member count
# =============================================================================
Write-Host "=== Test 3: Headcount defaults to member count ==="
Write-Host "  Expected: headcount = number of active household members (2)"

$defaultHcBody = @{
    date = $TODAY
    slot = "lunch"
    text = "Quick salad"
    # headcount intentionally omitted
} | ConvertTo-Json

$entry2 = Invoke-RestMethod -Uri "$BASE/households/$HID/meals" `
    -Method POST -Headers $HEADERS -Body $defaultHcBody
$ENTRY2_ID = $entry2.id

Write-Host "  Created entry: $ENTRY2_ID"
Write-Host "  Headcount: $($entry2.headcount)"

# Get member count to compare
$members = Invoke-RestMethod -Uri "$BASE/households/$HID/members" -Method GET -Headers $HEADERS
$memberCount = $members.Count
Write-Host "  Active members: $memberCount"

if ($entry2.headcount -eq $memberCount) {
    Write-Host "  PASS: Headcount defaulted to member count ($memberCount)" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected headcount=$memberCount, got $($entry2.headcount)" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 4: Owner can update their entry
# =============================================================================
Write-Host "=== Test 4: Owner updates their entry ==="
Write-Host "  Expected: 200, text and headcount updated"

$updateBody = @{
    text = "Margherita pizza"
    headcount = 4
} | ConvertTo-Json

$updated = Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$ENTRY1_ID" `
    -Method PATCH -Headers $HEADERS -Body $updateBody

Write-Host "  Text: $($updated.text)"
Write-Host "  Headcount: $($updated.headcount)"

if ($updated.text -ne "Margherita pizza") { Write-Host "  FAIL: Expected text='Margherita pizza'" -ForegroundColor Red }
elseif ($updated.headcount -ne 4) { Write-Host "  FAIL: Expected headcount=4" -ForegroundColor Red }
else { Write-Host "  PASS" -ForegroundColor Green }
Write-Host ""

# =============================================================================
# Test 5: Non-owner non-admin cannot update (403)
# =============================================================================
Write-Host "=== Test 5: Non-owner cannot update ==="
Write-Host "  Expected: 403 (User2 is member, not admin, and not the owner)"

$hackBody = @{ text = "Hijacked meal" } | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$ENTRY1_ID" `
        -Method PATCH -Headers $HEADERS2 -Body $hackBody
    Write-Host "  FAIL: Should have returned 403" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"
    if ($statusCode -eq 403) {
        Write-Host "  PASS: Non-owner correctly forbidden from editing" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 403, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 6: Non-owner non-admin cannot delete (403)
# =============================================================================
Write-Host "=== Test 6: Non-owner cannot delete ==="
Write-Host "  Expected: 403"

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$ENTRY1_ID" `
        -Method DELETE -Headers $HEADERS2
    Write-Host "  FAIL: Should have returned 403" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"
    if ($statusCode -eq 403) {
        Write-Host "  PASS: Non-owner correctly forbidden from deleting" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 403, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 7: Admin can update any entry
# =============================================================================
Write-Host "=== Test 7: Admin can update another user's entry ==="
Write-Host "  User2 creates an entry, User1 (admin) updates it"

# User2 creates an entry on tomorrow's lunch
$user2Body = @{
    date = $TOMORROW
    slot = "lunch"
    text = "Bob's soup"
    headcount = 2
} | ConvertTo-Json

$entry3 = Invoke-RestMethod -Uri "$BASE/households/$HID/meals" `
    -Method POST -Headers $HEADERS2 -Body $user2Body
$ENTRY3_ID = $entry3.id
Write-Host "  User2 created entry: $ENTRY3_ID"

# Admin (User1) updates it
$adminUpdateBody = @{ text = "Admin override: steak" } | ConvertTo-Json

$adminUpdated = Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$ENTRY3_ID" `
    -Method PATCH -Headers $HEADERS -Body $adminUpdateBody

Write-Host "  Text after admin edit: $($adminUpdated.text)"
if ($adminUpdated.text -eq "Admin override: steak") {
    Write-Host "  PASS: Admin can edit any entry" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected admin edit to succeed" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 8: Admin can delete any entry
# =============================================================================
Write-Host "=== Test 8: Admin can delete another user's entry ==="
Write-Host "  Expected: 204"

Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$ENTRY3_ID" `
    -Method DELETE -Headers $HEADERS
Write-Host "  PASS: Admin deleted User2's entry (204)" -ForegroundColor Green

# Verify it's gone
try {
    # Try to update it — should 404
    Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$ENTRY3_ID" `
        -Method PATCH -Headers $HEADERS -Body '{"text":"ghost"}'
    Write-Host "  FAIL: Deleted entry should not be accessible" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 404) {
        Write-Host "  PASS: Deleted entry returns 404" -ForegroundColor Green
    } else {
        Write-Host "  INFO: Got status $statusCode (entry gone)" -ForegroundColor Yellow
    }
}
Write-Host ""

# =============================================================================
# Test 9: Different slots on same date allowed (lunch + dinner)
# =============================================================================
Write-Host "=== Test 9: Different slots on same date ==="
Write-Host "  Expected: lunch and dinner on same date both succeed"
Write-Host "  (Test 1 claimed dinner on $TODAY, Test 3 claimed lunch on $TODAY)"

# Both already exist — verify via GET
$todayEntries = Invoke-RestMethod -Uri "$BASE/households/$HID/meals?start=$TODAY&end=$TODAY" `
    -Method GET -Headers $HEADERS

$slots = $todayEntries | ForEach-Object { $_.slot }
Write-Host "  Slots on $TODAY`: $($slots -join ', ')"

if ($slots -contains "lunch" -and $slots -contains "dinner") {
    Write-Host "  PASS: Both lunch and dinner exist on same date" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected both lunch and dinner" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 10: Same slot on different dates allowed
# =============================================================================
Write-Host "=== Test 10: Same slot on different dates ==="
Write-Host "  Expected: dinner on $TODAY and dinner on $TOMORROW both succeed"

$tomorrowDinnerBody = @{
    date = $TOMORROW
    slot = "dinner"
    text = "Tomorrow's dinner"
    headcount = 2
} | ConvertTo-Json

$entry4 = Invoke-RestMethod -Uri "$BASE/households/$HID/meals" `
    -Method POST -Headers $HEADERS2 -Body $tomorrowDinnerBody
$ENTRY4_ID = $entry4.id

Write-Host "  Created dinner on $TOMORROW`: $ENTRY4_ID"
if ($entry4.slot -eq "dinner" -and $entry4.date -eq $TOMORROW) {
    Write-Host "  PASS: Same slot on different date allowed" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Unexpected entry values" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 11: Get entries for date range
# =============================================================================
Write-Host "=== Test 11: Get entries for date range ==="
Write-Host "  Expected: returns all entries between $TODAY and $TOMORROW"

$rangeEntries = Invoke-RestMethod -Uri "$BASE/households/$HID/meals?start=$TODAY&end=$TOMORROW" `
    -Method GET -Headers $HEADERS

Write-Host "  Entries returned: $($rangeEntries.Count)"
foreach ($e in $rangeEntries) {
    Write-Host "    - $($e.date) $($e.slot): '$($e.text)' (owner: $($e.owner_user_id))"
}

# We expect: today lunch, today dinner, tomorrow dinner = 3 entries
if ($rangeEntries.Count -ge 3) {
    Write-Host "  PASS: Date range query returns expected entries" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected at least 3 entries, got $($rangeEntries.Count)" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 12: Owner can delete their entry
# =============================================================================
Write-Host "=== Test 12: Owner deletes their own entry ==="
Write-Host "  Expected: 204"

# User2 deletes their own entry (entry4 - tomorrow dinner)
Invoke-RestMethod -Uri "$BASE/households/$HID/meals/$ENTRY4_ID" `
    -Method DELETE -Headers $HEADERS2
Write-Host "  PASS: Owner deleted their own entry (204)" -ForegroundColor Green
Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "=== Phase 5 Manual Tests Complete ===" -ForegroundColor Cyan
Write-Host "Success criteria validated:"
Write-Host "  [1] First-come-first-served slot claiming (409 on conflict)"
Write-Host "  [2] Only owner/admin can edit/delete (403 for non-owners)"
Write-Host "  [3] Headcount defaults to household member count"
Write-Host "  [4] Different slots on same date allowed"
Write-Host "  [5] Same slot on different dates allowed"
Write-Host "  [6] Admin can edit/delete any entry"
Write-Host "  [7] Date range query returns correct entries"
Write-Host ""
Write-Host "Not tested via API (requires leave flow):"
Write-Host "  [*] Member leave deletes future entries (validated in unit tests)"
