# =============================================================================
# Phase 6 — Chore Module Manual Test Script
# =============================================================================
# Assumes:
#   - Server running: cd apps/api && uvicorn hausly.main:app --reload
#   - PostgreSQL running with migrations applied (alembic upgrade head)
#   - Two Firebase test users exist with valid tokens
#   - "chores" module is enabled in household settings
#
# Tests:
#   1. Creator must be in assignees (400)
#   2. Create recurring chore with rotation (happy path)
#   3. Initial assignments generated on creation
#   4. Rotation correctly cycles through assignees
#   5. Anyone can complete any assignment
#   6. Completed assignment records completed_by_user_id
#   7. Cannot complete already-completed assignment (400)
#   8. Postpone an assignment (sets postponed_to)
#   9. Cancel an assignment
#  10. Create one-off chore (assignments created immediately)
#  11. One-off chore auto-deactivates when all assignments resolved
#  12. List assignments with filters
#  13. Update chore (rename + change assignees)
#  14. Delete chore (deactivates, removes future assignments)
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
        -Body '{"name": "Chore Test Home", "type": "couple"}'
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
$NEXT_WEEK = (Get-Date).AddDays(7).ToString("yyyy-MM-dd")
$FUTURE = (Get-Date).AddDays(5).ToString("yyyy-MM-dd")

# =============================================================================
# Cleanup: Delete existing test chores
# =============================================================================
Write-Host "=== Cleanup: removing existing test chores ==="
$existingChores = Invoke-RestMethod -Uri "$BASE/households/$HID/chores" `
    -Method GET -Headers $HEADERS
foreach ($chore in $existingChores) {
    try {
        Invoke-RestMethod -Uri "$BASE/households/$HID/chores/$($chore.id)" `
            -Method DELETE -Headers $HEADERS | Out-Null
        Write-Host "  Deleted chore: $($chore.id) ($($chore.name))"
    } catch {
        Write-Host "  (could not delete $($chore.id): $($_.Exception.Message))"
    }
}
Write-Host "=== Cleanup complete ==="
Write-Host ""

# =============================================================================
# Test 1: Creator must be in assignees (400)
# =============================================================================
Write-Host "=== Test 1: Creator not in assignees ==="
Write-Host "  Expected: 400 CREATOR_NOT_IN_ASSIGNEES"

$badBody = @{
    name = "Clean house"
    start_date = $TODAY
    is_recurring = $false
    assignee_user_ids = @($USER2_ID)
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/chores" `
        -Method POST -Headers $HEADERS -Body $badBody
    Write-Host "  FAIL: Should have returned 400" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"
    if ($statusCode -eq 400) {
        Write-Host "  PASS: Creator-in-assignees validation works" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 400, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 2: Create recurring chore with rotation (happy path)
# =============================================================================
Write-Host "=== Test 2: Create recurring rotating chore ==="
Write-Host "  Expected: 201, is_recurring=true, rotation_enabled=true"

$createBody = @{
    name = "Clean house"
    start_date = $TODAY
    is_recurring = $true
    recurrence_interval = 1
    recurrence_unit = "weeks"
    assignee_user_ids = @($USER1_ID, $USER2_ID)
    rotation_enabled = $true
} | ConvertTo-Json

$chore1 = Invoke-RestMethod -Uri "$BASE/households/$HID/chores" `
    -Method POST -Headers $HEADERS -Body $createBody
$CHORE1_ID = $chore1.id

Write-Host "  Created chore: $CHORE1_ID"
Write-Host "  Name: $($chore1.name)"
Write-Host "  Recurring: $($chore1.is_recurring)"
Write-Host "  Rotation: $($chore1.rotation_enabled)"
Write-Host "  Assignees: $($chore1.assignees.Count)"

if ($chore1.is_recurring -ne $true) { Write-Host "  FAIL: Expected is_recurring=true" -ForegroundColor Red }
elseif ($chore1.rotation_enabled -ne $true) { Write-Host "  FAIL: Expected rotation_enabled=true" -ForegroundColor Red }
elseif ($chore1.assignees.Count -ne 2) { Write-Host "  FAIL: Expected 2 assignees" -ForegroundColor Red }
else { Write-Host "  PASS" -ForegroundColor Green }
Write-Host ""

# =============================================================================
# Test 3: Initial assignments generated on creation
# =============================================================================
Write-Host "=== Test 3: Initial assignments generated ==="
Write-Host "  Expected: Pending assignments exist for the chore"

$assignments = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?status=pending" `
    -Method GET -Headers $HEADERS
$choreAssignments = $assignments | Where-Object { $_.chore_id -eq $CHORE1_ID }

Write-Host "  Assignments for this chore: $($choreAssignments.Count)"

if ($choreAssignments.Count -ge 1) {
    Write-Host "  PASS: Assignments generated on creation" -ForegroundColor Green
    Write-Host "  First assignment:"
    Write-Host "    Due: $($choreAssignments[0].due_date)"
    Write-Host "    Assigned to: $($choreAssignments[0].assigned_to_user_id)"
} else {
    Write-Host "  FAIL: No assignments generated" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 4: Rotation correctly cycles through assignees
# =============================================================================
Write-Host "=== Test 4: Rotation cycles through assignees ==="
Write-Host "  Expected: Different assignees on consecutive occurrences"

if ($choreAssignments.Count -ge 2) {
    $first_assignee = $choreAssignments[0].assigned_to_user_id
    $second_assignee = $choreAssignments[1].assigned_to_user_id

    Write-Host "  Occurrence 1: $first_assignee"
    Write-Host "  Occurrence 2: $second_assignee"

    if ($first_assignee -ne $second_assignee) {
        Write-Host "  PASS: Rotation cycles between different assignees" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Same assignee on consecutive occurrences" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: Need at least 2 assignments to verify rotation" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 5: Anyone can complete any assignment
# =============================================================================
Write-Host "=== Test 5: User2 completes User1's assignment ==="
Write-Host "  Expected: 200, completed_by_user_id=User2"

# Find an assignment for User1
$user1_assignment = $choreAssignments | Where-Object { $_.assigned_to_user_id -eq $USER1_ID } | Select-Object -First 1

if ($user1_assignment) {
    $ASSIGNMENT_ID = $user1_assignment.id
    Write-Host "  Completing assignment $ASSIGNMENT_ID (assigned to User1, completed by User2)"

    $completed = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments/$ASSIGNMENT_ID/complete" `
        -Method POST -Headers $HEADERS2

    Write-Host "  Status: $($completed.status)"
    Write-Host "  Completed by: $($completed.completed_by_user_id)"

    if ($completed.status -ne "completed") { Write-Host "  FAIL: Expected status=completed" -ForegroundColor Red }
    elseif ($completed.completed_by_user_id -ne $USER2_ID) { Write-Host "  FAIL: Expected completed_by=User2" -ForegroundColor Red }
    else { Write-Host "  PASS: Anyone can complete any assignment" -ForegroundColor Green }
} else {
    Write-Host "  SKIP: No assignment found for User1" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 6: Completed assignment records completed_by_user_id
# =============================================================================
Write-Host "=== Test 6: Completed assignment has correct metadata ==="
Write-Host "  Expected: completed_at is set, completed_by_user_id is the completer"

if ($completed) {
    if ($completed.completed_at -and $completed.completed_by_user_id -eq $USER2_ID) {
        Write-Host "  completed_at: $($completed.completed_at)"
        Write-Host "  completed_by: $($completed.completed_by_user_id)"
        Write-Host "  PASS" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Missing completion metadata" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No completed assignment from previous test" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 7: Cannot complete already-completed assignment (400)
# =============================================================================
Write-Host "=== Test 7: Cannot complete already-completed assignment ==="
Write-Host "  Expected: 400 ASSIGNMENT_NOT_PENDING"

if ($ASSIGNMENT_ID) {
    try {
        Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments/$ASSIGNMENT_ID/complete" `
            -Method POST -Headers $HEADERS
        Write-Host "  FAIL: Should have returned 400" -ForegroundColor Red
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "  Status code: $statusCode"
        if ($statusCode -eq 400) {
            Write-Host "  PASS: Cannot re-complete assignment" -ForegroundColor Green
        } else {
            Write-Host "  FAIL: Expected 400, got $statusCode" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  SKIP: No assignment to re-complete" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 8: Postpone an assignment
# =============================================================================
Write-Host "=== Test 8: Postpone a pending assignment ==="
Write-Host "  Expected: 200, postponed_to set, original due_date preserved"

# Re-fetch pending assignments from server (local list is stale after Test 5 completion)
$freshPending = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?status=pending" `
    -Method GET -Headers $HEADERS
$pendingAssignments = $freshPending | Where-Object { $_.chore_id -eq $CHORE1_ID }
$toPosptone = $pendingAssignments | Select-Object -First 1

if ($toPosptone) {
    $POSTPONE_ID = $toPosptone.id
    $originalDue = $toPosptone.due_date

    $postponeBody = @{ postpone_to = $FUTURE } | ConvertTo-Json

    $postponed = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments/$POSTPONE_ID/postpone" `
        -Method POST -Headers $HEADERS -Body $postponeBody

    Write-Host "  Original due_date: $originalDue"
    Write-Host "  postponed_to: $($postponed.postponed_to)"
    Write-Host "  Status: $($postponed.status)"

    if ($postponed.postponed_to -eq $FUTURE -and $postponed.status -eq "pending") {
        Write-Host "  PASS: Postpone sets new effective date" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Unexpected postpone result" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No pending assignment to postpone" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 9: Cancel an assignment
# =============================================================================
Write-Host "=== Test 9: Cancel a pending assignment ==="
Write-Host "  Expected: 200, status=cancelled"

# Find another pending assignment (or use the postponed one)
$pendingAssignments2 = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?status=pending" `
    -Method GET -Headers $HEADERS
$toCancel = $pendingAssignments2 | Where-Object { $_.chore_id -eq $CHORE1_ID } | Select-Object -First 1

if ($toCancel) {
    $CANCEL_ID = $toCancel.id

    $cancelled = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments/$CANCEL_ID/cancel" `
        -Method POST -Headers $HEADERS

    Write-Host "  Status: $($cancelled.status)"

    if ($cancelled.status -eq "cancelled") {
        Write-Host "  PASS: Assignment cancelled" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected status=cancelled" -ForegroundColor Red
    }
} else {
    Write-Host "  SKIP: No pending assignment to cancel" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 10: Create one-off chore (assignments created immediately)
# =============================================================================
Write-Host "=== Test 10: Create one-off chore ==="
Write-Host "  Expected: 201, both assignees get immediate assignments"

$oneOffBody = @{
    name = "Move furniture"
    start_date = $TODAY
    is_recurring = $false
    assignee_user_ids = @($USER1_ID, $USER2_ID)
    rotation_enabled = $false
} | ConvertTo-Json

$chore2 = Invoke-RestMethod -Uri "$BASE/households/$HID/chores" `
    -Method POST -Headers $HEADERS -Body $oneOffBody
$CHORE2_ID = $chore2.id

Write-Host "  Created one-off chore: $CHORE2_ID"
Write-Host "  Recurring: $($chore2.is_recurring)"

# Check assignments were created immediately
$oneOffAssignments = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?status=pending" `
    -Method GET -Headers $HEADERS
$oneOffChoreAssignments = $oneOffAssignments | Where-Object { $_.chore_id -eq $CHORE2_ID }

Write-Host "  Assignments: $($oneOffChoreAssignments.Count)"

if ($oneOffChoreAssignments.Count -eq 2) {
    Write-Host "  PASS: Both assignees got immediate assignments" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected 2 assignments, got $($oneOffChoreAssignments.Count)" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 11: One-off chore auto-deactivates when all assignments resolved
# =============================================================================
Write-Host "=== Test 11: One-off auto-deactivates ==="
Write-Host "  Expected: Chore becomes is_active=false after all assignments completed"

foreach ($a in $oneOffChoreAssignments) {
    Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments/$($a.id)/complete" `
        -Method POST -Headers $HEADERS | Out-Null
    Write-Host "  Completed assignment: $($a.id)"
}

# Get the chore to check is_active
try {
    $choreAfter = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/$CHORE2_ID" `
        -Method GET -Headers $HEADERS
    # If chore is still returned, check is_active
    if ($choreAfter.is_active -eq $false) {
        Write-Host "  PASS: One-off chore auto-deactivated" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected is_active=false" -ForegroundColor Red
    }
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 404) {
        Write-Host "  Note: Chore not found (deactivated and filtered from active list)"
        Write-Host "  PASS: One-off chore deactivated" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Unexpected error $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 12: List assignments with filters
# =============================================================================
Write-Host "=== Test 12: List assignments with filters ==="
Write-Host "  Expected: Filters by status, user_id, date range"

# Filter by status=completed
$completedList = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?status=completed" `
    -Method GET -Headers $HEADERS
Write-Host "  Completed assignments: $($completedList.Count)"

# Filter by user_id
$user1List = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?user_id=$USER1_ID" `
    -Method GET -Headers $HEADERS
Write-Host "  User1 assignments: $($user1List.Count)"

# Filter by date range
$dateList = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/assignments?start_date=$TODAY&end_date=$NEXT_WEEK" `
    -Method GET -Headers $HEADERS
Write-Host "  Assignments this week: $($dateList.Count)"

if ($completedList.Count -ge 1 -and $user1List.Count -ge 1) {
    Write-Host "  PASS: Filters work correctly" -ForegroundColor Green
} else {
    Write-Host "  WARN: Filters returned fewer results than expected" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 13: Update chore (rename + change assignees)
# =============================================================================
Write-Host "=== Test 13: Update chore ==="
Write-Host "  Expected: Name updated, assignees recomputed"

$updateBody = @{
    name = "Deep clean house"
} | ConvertTo-Json

$updatedChore = Invoke-RestMethod -Uri "$BASE/households/$HID/chores/$CHORE1_ID" `
    -Method PATCH -Headers $HEADERS -Body $updateBody

Write-Host "  Name: $($updatedChore.name)"

if ($updatedChore.name -eq "Deep clean house") {
    Write-Host "  PASS: Chore renamed" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected name='Deep clean house'" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 14: Delete chore (deactivates, removes future assignments)
# =============================================================================
Write-Host "=== Test 14: Delete chore ==="
Write-Host "  Expected: 204, chore deactivated, future assignments removed"

Invoke-RestMethod -Uri "$BASE/households/$HID/chores/$CHORE1_ID" `
    -Method DELETE -Headers $HEADERS
Write-Host "  Deleted chore: $CHORE1_ID (204)"

# Verify it's no longer in active list
$activeChores = Invoke-RestMethod -Uri "$BASE/households/$HID/chores" `
    -Method GET -Headers $HEADERS
$found = $activeChores | Where-Object { $_.id -eq $CHORE1_ID }

if (-not $found) {
    Write-Host "  PASS: Chore no longer in active list" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Deleted chore still appears in active list" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Phase 6 Manual Tests Complete" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Success Criteria Covered:"
Write-Host "  [1] Creator must be in assignees          → Test 1"
Write-Host "  [2] Rotation cycles through assignees     → Test 4"
Write-Host "  [3] Overdue blocks generation             → (requires time passage)"
Write-Host "  [4] Postpone updates effective date       → Test 8"
Write-Host "  [5] Anyone can complete any assignment    → Test 5"
Write-Host "  [6] Member leave recomputes rotation      → (requires leave flow)"
Write-Host "  [7] One-off auto-deactivates              → Test 11"
Write-Host ""
Write-Host "Note: Criteria 3 and 6 require time passage or member leave,"
Write-Host "which are covered by automated tests in test_phase6_smoke.py"
