# =============================================================================
# Phase 4 — Expense Module Manual Test Script
# =============================================================================
# Assumes:
#   - Server running: cd apps/api && uvicorn hausly.main:app --reload
#   - PostgreSQL running with migrations applied (alembic upgrade head)
#   - Two Firebase test users exist with valid tokens
#   - "expense" module is enabled in household settings
#
# Tests:
#   1. Create draft expense (validates splits sum == amount)
#   2. Splits validation rejects mismatched amounts (422)
#   3. Balances empty while only drafts exist
#   4. Confirm expense → status transitions to confirmed
#   5. Balances now reflect confirmed expense
#   6. Settlement suggestions minimize transactions
#   7. Settle a split
#   8. Confirmed expense cannot be updated (400)
#   9. Confirmed expense cannot be deleted (400)
#  10. Delete a draft expense (204)
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Configuration ---
$first_user_token = "<first-user-token"
$second_user_token = "<second-user-token>"
$HEADERS = @{ "Authorization" = "Bearer $first_user_token"; "Content-Type" = "application/json" }
$HEADERS2 = @{ "Authorization" = "Bearer $second_user_token"; "Content-Type" = "application/json" }
$BASE = "http://localhost:8000/api/v1"

# =============================================================================
# Setup: Verify users and get/create household
# =============================================================================
Write-Host "=== Setup: Verifying users and household ==="

# Verify user 1
$user1 = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS
$USER1_ID = $user1.user_id
Write-Host "User 1: $($user1.display_name) ($USER1_ID)"

# Verify user 2
$user2 = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS2
$USER2_ID = $user2.user_id
Write-Host "User 2: $($user2.display_name) ($USER2_ID)"

# Get or create household
if ($user1.households -and $user1.households.Count -gt 0) {
    $HID = $user1.households[0].id
    Write-Host "Using existing household: $HID"
} else {
    Write-Host "Creating new household..."
    $household = Invoke-RestMethod -Uri "$BASE/households" `
        -Method POST -Headers $HEADERS `
        -Body '{"name": "Expense Test Home", "type": "couple"}'
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
# Cleanup: Settle all unsettled splits + delete drafts → balances start at 0
# =============================================================================
Write-Host "=== Cleanup: zeroing balances ==="
$existingExpenses = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
    -Method GET -Headers $HEADERS
foreach ($ex in $existingExpenses) {
    if ($ex.status -eq "draft") {
        try {
            Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$($ex.id)" `
                -Method DELETE -Headers $HEADERS | Out-Null
            Write-Host "  Deleted draft: $($ex.id)"
        } catch {
            Write-Host "  (could not delete $($ex.id): $($_.Exception.Message))"
        }
    } else {
        # Settle all unsettled splits so they don't pollute balance calculations
        $detail = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$($ex.id)" `
            -Method GET -Headers $HEADERS
        foreach ($sp in $detail.splits) {
            if ($sp.is_settled -eq $false) {
                try {
                    Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/splits/$($sp.id)/settle" `
                        -Method POST -Headers $HEADERS | Out-Null
                    Write-Host "  Settled split $($sp.id) on confirmed expense $($ex.id)"
                } catch {
                    Write-Host "  (could not settle $($sp.id): $($_.Exception.Message))"
                }
            }
        }
    }
}
# Verify balances are now 0
$cleanCheck = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/balances" -Method GET -Headers $HEADERS
if ($cleanCheck.balances.Count -eq 0) {
    Write-Host "=== Cleanup complete: balances zeroed ===" -ForegroundColor Green
} else {
    Write-Host "=== WARNING: $($cleanCheck.balances.Count) balance(s) remain after cleanup ===" -ForegroundColor Yellow
}
Write-Host ""

# =============================================================================
# Test 1: Create a draft expense (happy path)
# =============================================================================
Write-Host "=== Test 1: Create draft expense ==="
Write-Host "  Expected: 201, status=draft, splits sum to amount"

$createBody = @{
    title = "Dinner at Mario's"
    amount = 60.00
    currency = "EUR"
    category = "food"
    paid_by_user_id = $USER1_ID
    splits = @(
        @{ user_id = $USER1_ID; share_amount = 30.00 },
        @{ user_id = $USER2_ID; share_amount = 30.00 }
    )
    status = "draft"
} | ConvertTo-Json -Depth 3

$expense = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
    -Method POST -Headers $HEADERS -Body $createBody
$EXPENSE_ID = $expense.id

Write-Host "  Created expense: $EXPENSE_ID"
Write-Host "  Status: $($expense.status)"  # Expected: draft
Write-Host "  Amount: $($expense.amount)"  # Expected: 60
Write-Host "  Splits count: $($expense.splits.Count)"  # Expected: 2

if ($expense.status -ne "draft") { Write-Host "  FAIL: Expected status=draft" -ForegroundColor Red }
if ($expense.amount -ne 60) { Write-Host "  FAIL: Expected amount=60" -ForegroundColor Red }
if ($expense.splits.Count -ne 2) { Write-Host "  FAIL: Expected 2 splits" -ForegroundColor Red }
if ($null -ne $expense.confirmed_at) { Write-Host "  FAIL: confirmed_at should be null for draft" -ForegroundColor Red }

Write-Host "  PASS" -ForegroundColor Green
Write-Host ""

# =============================================================================
# Test 2: Splits validation rejects mismatch (splits don't sum to amount)
# =============================================================================
Write-Host "=== Test 2: Splits validation rejects mismatch ==="
Write-Host "  Expected: 422, sum of splits (60) != amount (40)"

$badBody = @{
    title = "Bad Split"
    amount = 40.00
    paid_by_user_id = $USER1_ID
    splits = @(
        @{ user_id = $USER1_ID; share_amount = 30.00 },
        @{ user_id = $USER2_ID; share_amount = 30.00 }
    )
    status = "draft"
} | ConvertTo-Json -Depth 3

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
        -Method POST -Headers $HEADERS -Body $badBody
    Write-Host "  FAIL: Should have returned 422" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"  # Expected: 422
    if ($statusCode -eq 422) {
        Write-Host "  PASS: Correctly rejected mismatched splits" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 422, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 3: Balances empty while only drafts exist
# =============================================================================
Write-Host "=== Test 3: Balances empty (only drafts) ==="
Write-Host "  Expected: empty balances array"

$balances = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/balances" `
    -Method GET -Headers $HEADERS

Write-Host "  Balances count: $($balances.balances.Count)"  # Expected: 0
if ($balances.balances.Count -eq 0) {
    Write-Host "  PASS: Drafts don't affect balances" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected 0 balances, got $($balances.balances.Count)" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 4: Confirm the expense
# =============================================================================
Write-Host "=== Test 4: Confirm expense ==="
Write-Host "  Expected: status=confirmed, confirmed_at set"

$confirmed = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE_ID/confirm" `
    -Method POST -Headers $HEADERS

Write-Host "  Status: $($confirmed.status)"  # Expected: confirmed
Write-Host "  Confirmed at: $($confirmed.confirmed_at)"

if ($confirmed.status -ne "confirmed") { Write-Host "  FAIL: Expected status=confirmed" -ForegroundColor Red }
elseif ($null -eq $confirmed.confirmed_at) { Write-Host "  FAIL: confirmed_at should be set" -ForegroundColor Red }
else { Write-Host "  PASS" -ForegroundColor Green }
Write-Host ""

# =============================================================================
# Test 4b: Create + confirm a second expense (User2 pays, more complex balance)
# =============================================================================
Write-Host "=== Test 4b: Create + confirm second expense (User2 pays) ==="
Write-Host "  User2 pays EUR 40, split equally (20/20)"
Write-Host "  After this: User2 owes User1 30, User1 owes User2 20 → net: User2 owes User1 10"

$createBody2 = @{
    title = "Taxi ride"
    amount = 40.00
    currency = "EUR"
    category = "transport"
    paid_by_user_id = $USER2_ID
    splits = @(
        @{ user_id = $USER1_ID; share_amount = 20.00 },
        @{ user_id = $USER2_ID; share_amount = 20.00 }
    )
    status = "draft"
} | ConvertTo-Json -Depth 3

$expense2 = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
    -Method POST -Headers $HEADERS -Body $createBody2
$EXPENSE2_ID = $expense2.id
Write-Host "  Created expense 2 (draft): $EXPENSE2_ID"

# Confirm it
$confirmed2 = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE2_ID/confirm" `
    -Method POST -Headers $HEADERS
Write-Host "  Confirmed expense 2: status=$($confirmed2.status)"

if ($confirmed2.status -eq "confirmed") {
    Write-Host "  PASS" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected confirmed" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 5: Balances reflect BOTH confirmed expenses (net calculation)
# =============================================================================
Write-Host "=== Test 5: Balances with multiple payers ==="
Write-Host "  Expected: net = 30 (User2 owes User1) - 20 (User1 owes User2) = 10"

$balances = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/balances" `
    -Method GET -Headers $HEADERS

Write-Host "  Balances count: $($balances.balances.Count)"  # Expected: 1
if ($balances.balances.Count -gt 0) {
    $b = $balances.balances[0]
    Write-Host "  Pair: $($b.user_a_id) / $($b.user_b_id)"
    Write-Host "  Net amount: $($b.net_amount)"  # Expected: 10.00
    Write-Host "  Direction: $($b.direction)"
    if ($b.net_amount -eq 10) {
        Write-Host "  PASS: Net balance correctly computed across multiple payers" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected net_amount=10, got $($b.net_amount)" -ForegroundColor Red
    }
} else {
    Write-Host "  FAIL: Expected 1 balance entry" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 6: Settlement suggestions (net amount)
# =============================================================================
Write-Host "=== Test 6: Settlement suggestions ==="
Write-Host "  Expected: 1 settlement — User2 pays User1 10.00 (net of both expenses)"

$settlements = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/settlements" `
    -Method GET -Headers $HEADERS

Write-Host "  Settlements count: $($settlements.settlements.Count)"  # Expected: 1
if ($settlements.settlements.Count -gt 0) {
    $s = $settlements.settlements[0]
    Write-Host "  From: $($s.from_user_id)"
    Write-Host "  To: $($s.to_user_id)"
    Write-Host "  Amount: $($s.amount)"  # Expected: 10.00
    if ($s.amount -eq 10) {
        Write-Host "  PASS: Settlement minimizes to net amount" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected amount=10, got $($s.amount)" -ForegroundColor Red
    }
} else {
    Write-Host "  FAIL: Expected 1 settlement" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 7: Settle all splits (both expenses)
# =============================================================================
Write-Host "=== Test 7: Settle all splits ==="
Write-Host "  Settling User2's split on expense 1 (owes User1 30)"
Write-Host "  Settling User1's split on expense 2 (owes User2 20)"

# Settle User2's split on expense 1
$exp1Detail = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE_ID" `
    -Method GET -Headers $HEADERS
$split1 = $exp1Detail.splits | Where-Object { $_.user_id -eq $USER2_ID }
Write-Host "  Settling split (exp1, User2): $($split1.id)"

$settled1 = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/splits/$($split1.id)/settle" `
    -Method POST -Headers $HEADERS

if ($settled1.is_settled -eq $true) {
    Write-Host "  PASS: Expense 1 split settled" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected is_settled=true" -ForegroundColor Red
}

# Settle User1's split on expense 2
$exp2Detail = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE2_ID" `
    -Method GET -Headers $HEADERS
$split2 = $exp2Detail.splits | Where-Object { $_.user_id -eq $USER1_ID }
Write-Host "  Settling split (exp2, User1): $($split2.id)"

$settled2 = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/splits/$($split2.id)/settle" `
    -Method POST -Headers $HEADERS

if ($settled2.is_settled -eq $true) {
    Write-Host "  PASS: Expense 2 split settled" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected is_settled=true" -ForegroundColor Red
}

# Verify balances are now empty (all cross-user splits settled)
$balancesAfter = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/balances" `
    -Method GET -Headers $HEADERS
Write-Host "  Balances after settling both: $($balancesAfter.balances.Count)"  # Expected: 0
if ($balancesAfter.balances.Count -eq 0) {
    Write-Host "  PASS: All settled — balances cleared" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected 0 balances after full settlement" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 7b: Unequal split — balance reflects asymmetric debt
# =============================================================================
Write-Host "=== Test 7b: Unequal split balance ==="
Write-Host "  User1 pays EUR 80, split: User1=65, User2=15"
Write-Host "  Expected balance: User2 owes User1 only 15 (payer's share self-cancels)"

$unequalBody = @{
    title = "Fancy dinner (unequal)"
    amount = 80.00
    currency = "EUR"
    category = "food"
    paid_by_user_id = $USER1_ID
    splits = @(
        @{ user_id = $USER1_ID; share_amount = 65.00 },
        @{ user_id = $USER2_ID; share_amount = 15.00 }
    )
    status = "confirmed"
} | ConvertTo-Json -Depth 3

$expUnequal = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
    -Method POST -Headers $HEADERS -Body $unequalBody
$EXP_UNEQUAL_ID = $expUnequal.id
Write-Host "  Created unequal expense: $EXP_UNEQUAL_ID"

# After Test 7 settled everything, this is the only unsettled expense → balance = 15
$balancesUnequal = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/balances" `
    -Method GET -Headers $HEADERS

Write-Host "  Net amount: $($balancesUnequal.balances[0].net_amount)"  # Expected: 15
if ($balancesUnequal.balances.Count -eq 1 -and $balancesUnequal.balances[0].net_amount -eq 15) {
    Write-Host "  PASS: Unequal split — only User2's 15 portion counts (payer's 65 self-cancels)" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected net_amount=15, got $($balancesUnequal.balances[0].net_amount)" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Test 8: Confirmed expense cannot be updated
# =============================================================================
Write-Host "=== Test 8: Cannot update confirmed expense ==="
Write-Host "  Expected: 400 CANNOT_EDIT_CONFIRMED"

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE_ID" `
        -Method PATCH -Headers $HEADERS `
        -Body '{"title": "Hacked Title"}'
    Write-Host "  FAIL: Should have returned 400" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"  # Expected: 400
    if ($statusCode -eq 400) {
        Write-Host "  PASS: Confirmed expense is immutable" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 400, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 9: Confirmed expense cannot be deleted
# =============================================================================
Write-Host "=== Test 9: Cannot delete confirmed expense ==="
Write-Host "  Expected: 400 CANNOT_DELETE_CONFIRMED"

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXPENSE_ID" `
        -Method DELETE -Headers $HEADERS
    Write-Host "  FAIL: Should have returned 400" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "  Status code: $statusCode"  # Expected: 400
    if ($statusCode -eq 400) {
        Write-Host "  PASS: Confirmed expense cannot be deleted" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 400, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 10: Delete a draft expense (happy path)
# =============================================================================
Write-Host "=== Test 10: Delete draft expense ==="
Write-Host "  Expected: 204 No Content"

# Create a new draft to delete
$draftBody = @{
    title = "To Be Deleted"
    amount = 20.00
    paid_by_user_id = $USER1_ID
    splits = @(
        @{ user_id = $USER1_ID; share_amount = 10.00 },
        @{ user_id = $USER2_ID; share_amount = 10.00 }
    )
    status = "draft"
} | ConvertTo-Json -Depth 3

$draftExpense = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
    -Method POST -Headers $HEADERS -Body $draftBody
$DRAFT_ID = $draftExpense.id
Write-Host "  Created draft to delete: $DRAFT_ID"

Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$DRAFT_ID" `
    -Method DELETE -Headers $HEADERS
Write-Host "  PASS: Draft deleted (204)" -ForegroundColor Green

# Verify it's gone
try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$DRAFT_ID" `
        -Method GET -Headers $HEADERS
    Write-Host "  FAIL: Should have returned 404" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 404) {
        Write-Host "  PASS: Deleted expense returns 404" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected 404, got $statusCode" -ForegroundColor Red
    }
}
Write-Host ""

# =============================================================================
# Test 11: New expense after settlement — balances computed fresh
# =============================================================================
Write-Host "=== Test 11: New expense after settlement cycle ==="
Write-Host "  Settling Test 7b's unequal split first, then adding new expense."
Write-Host "  User1 pays EUR 50, split 25/25 → User2 owes User1 25 (new debt only)"

# Settle the unsettled split from Test 7b so we start from 0
$expUnequalDetail = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/$EXP_UNEQUAL_ID" `
    -Method GET -Headers $HEADERS
foreach ($sp in $expUnequalDetail.splits) {
    if ($sp.is_settled -eq $false) {
        Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/splits/$($sp.id)/settle" `
            -Method POST -Headers $HEADERS | Out-Null
    }
}
Write-Host "  Settled Test 7b splits — balances now at 0"

$postSettleBody = @{
    title = "Groceries after settle-up"
    amount = 50.00
    currency = "EUR"
    category = "food"
    paid_by_user_id = $USER1_ID
    splits = @(
        @{ user_id = $USER1_ID; share_amount = 25.00 },
        @{ user_id = $USER2_ID; share_amount = 25.00 }
    )
    status = "confirmed"
    source = "manual"
} | ConvertTo-Json -Depth 3

$expense3 = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses" `
    -Method POST -Headers $HEADERS -Body $postSettleBody
$EXPENSE3_ID = $expense3.id
Write-Host "  Created + confirmed expense 3: $EXPENSE3_ID"

# Check balances — should only reflect the new expense (old ones settled)
$balancesNew = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/balances" `
    -Method GET -Headers $HEADERS

Write-Host "  Balances count: $($balancesNew.balances.Count)"  # Expected: 1
if ($balancesNew.balances.Count -gt 0) {
    $bn = $balancesNew.balances[0]
    Write-Host "  Net amount: $($bn.net_amount)"  # Expected: 25.00
    Write-Host "  Direction: $($bn.direction)"
    if ($bn.net_amount -eq 25) {
        Write-Host "  PASS: New expense creates fresh balance, settled data ignored" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Expected net_amount=25 (only new expense), got $($bn.net_amount)" -ForegroundColor Red
    }
} else {
    Write-Host "  FAIL: Expected 1 balance entry from new expense" -ForegroundColor Red
}

# Verify settlement suggestion reflects only the new debt
$settlementsNew = Invoke-RestMethod -Uri "$BASE/households/$HID/expenses/settlements" `
    -Method GET -Headers $HEADERS
Write-Host "  Settlement: $($settlementsNew.settlements.Count) suggestion(s)"
if ($settlementsNew.settlements.Count -eq 1 -and $settlementsNew.settlements[0].amount -eq 25) {
    Write-Host "  PASS: Settlement only considers unsettled splits" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Expected 1 settlement of 25" -ForegroundColor Red
}
Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "=== Phase 4 Manual Tests Complete ===" -ForegroundColor Cyan
Write-Host "Success criteria validated:"
Write-Host "  [1] Create expense validates sum(splits) == amount"
Write-Host "  [2] Only confirmed expenses affect balances"
Write-Host "  [3] Draft->confirm flow works"
Write-Host "  [4] Balance calculation correct with multiple payers (net)"
Write-Host "  [5] Settlement algorithm minimizes to net amount"
Write-Host "  [6] Settle split marks is_settled=true, clears balances"
Write-Host "  [7] Confirmed expenses are immutable (no update/delete)"
Write-Host "  [8] Draft expenses can be deleted"
Write-Host "  [9] New expenses after settlement compute fresh balances"

