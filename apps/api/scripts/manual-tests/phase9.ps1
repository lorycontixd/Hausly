# =============================================================================
# Phase 9 — Mobile Auth & API Client Contract Smoke Test
# =============================================================================
# Assumes:
#   - Server running: cd apps/api && uvicorn hausly.main:app --reload
#   - PostgreSQL running with migrations applied (alembic upgrade head)
#   - Two Firebase test users exist with valid tokens
#
# What this script verifies (from the mobile app's perspective):
#   1. Auth/verify endpoint returns correct shape (VerifyResponse)
#   2. Unauthenticated requests get 401 (mobile shows login screen)
#   3. Invalid token gets 401 (mobile redirects to login)
#   4. Auth token injection works (Authorization: Bearer <token>)
#   5. Onboarding: create household returns expected shape
#   6. Onboarding: join household with invite code works
#   7. After join, auth/verify shows household in response (mobile redirects to tabs)
#   8. API error shape matches mobile's ApiError interface ({ detail, code? })
#
# Maps to Phase 9 Success Criteria:
#   - User can sign in with Google/Apple → verified via token + /auth/verify
#   - Auth state persists across app restarts → Firebase handles; we verify token works
#   - API calls include valid auth token → Tests 1, 4
#   - Unauthenticated users see login screen → Tests 2, 3
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Configuration ---
$first_user_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6Ijc5OTRiNGYzMTU2MzJiMjk3NzAwNmQ5M2U5NGIyYWNiZTMwNWZlNDYiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vaGF1c2x5LTMzMzhlIiwiYXVkIjoiaGF1c2x5LTMzMzhlIiwiYXV0aF90aW1lIjoxNzgxMTAwNDYyLCJ1c2VyX2lkIjoiZ1V5SUxVZGJOamRSMUNzNGdsSnBiUUMyMlVyMSIsInN1YiI6ImdVeUlMVWRiTmpkUjFDczRnbEpwYlFDMjJVcjEiLCJpYXQiOjE3ODExMDA0NjIsImV4cCI6MTc4MTEwNDA2MiwiZW1haWwiOiJ0ZXN0dXNlcjFAdGVzdC5jb20iLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZW1haWwiOlsidGVzdHVzZXIxQHRlc3QuY29tIl19LCJzaWduX2luX3Byb3ZpZGVyIjoicGFzc3dvcmQifX0.YlaNXehYj9VbWVJJ4VlPQYbJ41dyfd_cMwfn49UktlxBmsM3OoH3QzmvEoG-7KtecnroYh1BVxOU_6eoJfIEIIQTllazIukx7YegkE83pPbN4acWtTfadWneNCOmhLlPDIO1zXk70KcIOcIbz-95tjmNqF37gpgLr0Pfdh6avD3B237SonKmd_RDgL_uuydQoj8Yysyd0UbS8QQdrVFzU8HeVf2Vn-fJck6bX6-rDUD9tTUmEpNSyhXLOoRTpZ27tMXrWW-BeJtVJqaEngOPh0L_DRVNay7LXDWcaRxtJVnKf-LqH5EdDhzq_tImes47Hqm_3j-P_sgUrhNmakNaTA"
$second_user_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6Ijc5OTRiNGYzMTU2MzJiMjk3NzAwNmQ5M2U5NGIyYWNiZTMwNWZlNDYiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vaGF1c2x5LTMzMzhlIiwiYXVkIjoiaGF1c2x5LTMzMzhlIiwiYXV0aF90aW1lIjoxNzgxMTAwNDkxLCJ1c2VyX2lkIjoiZVFya3puSGxibVp0WEE4MUJjbk1qYnBqNklvMSIsInN1YiI6ImVRcmt6bkhsYm1adFhBODFCY25NamJwajZJbzEiLCJpYXQiOjE3ODExMDA0OTEsImV4cCI6MTc4MTEwNDA5MSwiZW1haWwiOiJ0ZXN0dXNlcjJAdGVzdC5jb20iLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZW1haWwiOlsidGVzdHVzZXIyQHRlc3QuY29tIl19LCJzaWduX2luX3Byb3ZpZGVyIjoicGFzc3dvcmQifX0.Gw9RjselhBeNUKcJ1i-MPXjjkm4y0HIDRrVpiR2FCpTkokPaSk7w50k2NjlnvsNLlq9p77_zb0zWQNb8PReA3p7kKZEuJ8I3lkZJclNc_mELkH3Z5HC7vDqhQoGkMh6kS8Ps7MXz7ZlKjgqODPI6YL2xwCMTm9e-USoJs-qJGDeReUSIaDiHoUM0ddl1UoNryZG32a57FDO_vGu7N5JtXwd7es6eYxeFfpD1KGo1iANhh2oasv4gwa35zSqzgKnTC_iLg1r0FQvmWRpf35ngtneGl98mHJRzmtRo09sVy1BKJV5yx_HSOPUB870lCgCy4BDQYNxcIjcCng4-QkPwBQ"
$HEADERS = @{ "Authorization" = "Bearer $first_user_token"; "Content-Type" = "application/json" }
$HEADERS2 = @{ "Authorization" = "Bearer $second_user_token"; "Content-Type" = "application/json" }
$BASE = "http://localhost:8000/api/v1"

$passed = 0
$failed = 0

function Assert-Pass($message) {
    $script:passed++
    Write-Host "  PASS: $message" -ForegroundColor Green
}

function Assert-Fail($message) {
    $script:failed++
    Write-Host "  FAIL: $message" -ForegroundColor Red
}

# =============================================================================
# Cleanup: remove users from any existing households
# =============================================================================
Write-Host "=== Setup: Cleaning existing memberships ==="

$user2_check = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS2
if ($user2_check.households -and $user2_check.households.Count -gt 0) {
    foreach ($h in $user2_check.households) {
        try {
            Invoke-RestMethod -Uri "$BASE/households/$($h.id)/leave" -Method POST -Headers $HEADERS2 | Out-Null
            Write-Host "  User 2 left household $($h.id)"
        } catch { Write-Host "  (User 2 leave failed: $($_.Exception.Message))" }
    }
}

$user1_check = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS
if ($user1_check.households -and $user1_check.households.Count -gt 0) {
    foreach ($h in $user1_check.households) {
        try {
            Invoke-RestMethod -Uri "$BASE/households/$($h.id)/leave" -Method POST -Headers $HEADERS | Out-Null
            Write-Host "  User 1 left household $($h.id)"
        } catch { Write-Host "  (User 1 leave failed: $($_.Exception.Message))" }
    }
}

Write-Host "=== Setup complete ==="
Write-Host ""

# =============================================================================
# Test 1: Auth/verify returns correct VerifyResponse shape
# =============================================================================
Write-Host "=== Test 1: /auth/verify returns VerifyResponse shape ==="
Write-Host "  Expected: { user_id, display_name, email, avatar_url, households[] }"
Write-Host "  Maps to: API calls include valid auth token"

$verifyResp = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS

$hasUserId = [bool]$verifyResp.user_id
$hasDisplayName = $null -ne $verifyResp.PSObject.Properties["display_name"]
$hasEmail = [bool]$verifyResp.email
$hasAvatarUrl = $null -ne $verifyResp.PSObject.Properties["avatar_url"]
$hasHouseholds = $null -ne $verifyResp.PSObject.Properties["households"]

Write-Host "  user_id: $($verifyResp.user_id)"
Write-Host "  display_name: $($verifyResp.display_name)"
Write-Host "  email: $($verifyResp.email)"
Write-Host "  avatar_url: $($verifyResp.avatar_url)"
Write-Host "  households: $($verifyResp.households.Count) entries"

if ($hasUserId -and $hasDisplayName -and $hasEmail -and $hasAvatarUrl -and $hasHouseholds) {
    Assert-Pass "VerifyResponse has all expected fields"
} else {
    Assert-Fail "VerifyResponse missing fields: userId=$hasUserId, displayName=$hasDisplayName, email=$hasEmail, avatarUrl=$hasAvatarUrl, households=$hasHouseholds"
}
Write-Host ""

# =============================================================================
# Test 2: Unauthenticated request returns 401
# =============================================================================
Write-Host "=== Test 2: Unauthenticated request returns 401 ==="
Write-Host "  Expected: 401 with { detail: '...' }"
Write-Host "  Maps to: Unauthenticated users see login screen"

try {
    $noAuthHeaders = @{ "Content-Type" = "application/json" }
    Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $noAuthHeaders
    Assert-Fail "Should have returned 401, but got success"
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 401) {
        Assert-Pass "Unauthenticated request returns 401"
    } else {
        Assert-Fail "Expected 401, got $statusCode"
    }
}
Write-Host ""

# =============================================================================
# Test 3: Invalid token returns 401
# =============================================================================
Write-Host "=== Test 3: Invalid/expired token returns 401 ==="
Write-Host "  Expected: 401 — mobile would redirect to login"
Write-Host "  Maps to: Unauthenticated users see login screen"

try {
    $badHeaders = @{ "Authorization" = "Bearer invalid_token_12345"; "Content-Type" = "application/json" }
    Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $badHeaders
    Assert-Fail "Should have returned 401 for invalid token"
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 401) {
        Assert-Pass "Invalid token returns 401"
    } else {
        Assert-Fail "Expected 401, got $statusCode"
    }
}
Write-Host ""

# =============================================================================
# Test 4: Authenticated user with no household (onboarding state)
# =============================================================================
Write-Host "=== Test 4: User with no household → mobile shows onboarding ==="
Write-Host "  Expected: households = [] (empty array)"
Write-Host "  Maps to: Auth state — no household → onboarding"

$freshUser = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS

if ($freshUser.households.Count -eq 0) {
    Assert-Pass "No households — mobile would show onboarding screen"
} else {
    Assert-Fail "Expected 0 households after cleanup, got $($freshUser.households.Count)"
}
Write-Host ""

# =============================================================================
# Test 5: Onboarding — create household (mobile's handleCreate)
# =============================================================================
Write-Host "=== Test 5: Create household via onboarding ==="
Write-Host "  Expected: 201 with { id, name, invite_code, ... }"
Write-Host "  Maps to: Onboarding flow — create new household"

$createBody = @{
    name = "Phase 9 Test Home"
    type = "couple"
} | ConvertTo-Json

$household = Invoke-RestMethod -Uri "$BASE/households" `
    -Method POST -Headers $HEADERS -Body $createBody
$HID = $household.id
$INVITE_CODE = $household.invite_code

Write-Host "  id: $HID"
Write-Host "  name: $($household.name)"
Write-Host "  invite_code: $INVITE_CODE"

$hasId = [bool]$household.id
$hasName = $household.name -eq "Phase 9 Test Home"
$hasInviteCode = [bool]$household.invite_code

if ($hasId -and $hasName -and $hasInviteCode) {
    Assert-Pass "Household created with expected shape"
} else {
    Assert-Fail "Missing fields: id=$hasId, name=$hasName, invite_code=$hasInviteCode"
}
Write-Host ""

# =============================================================================
# Test 6: After create, verify shows household in response
# =============================================================================
Write-Host "=== Test 6: After create, /auth/verify includes the household ==="
Write-Host "  Expected: households[0].id matches created household"
Write-Host "  Maps to: Auth state — hasHousehold=true → redirect to tabs"

$afterCreate = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS

if ($afterCreate.households.Count -ge 1 -and $afterCreate.households[0].id -eq $HID) {
    Assert-Pass "Verify now shows household — mobile would redirect to (tabs)"
} else {
    Assert-Fail "Expected household $HID in verify response, got: $($afterCreate.households | ConvertTo-Json -Compress)"
}
Write-Host ""

# =============================================================================
# Test 7: Onboarding — join household with invite code (mobile's handleJoin)
# =============================================================================
Write-Host "=== Test 7: Join household via invite code ==="
Write-Host "  Expected: User 2 joins, verify shows household"
Write-Host "  Maps to: Onboarding flow — join with invite code"

$joinBody = @{ invite_code = $INVITE_CODE } | ConvertTo-Json
$joinResp = Invoke-RestMethod -Uri "$BASE/households/join" `
    -Method POST -Headers $HEADERS2 -Body $joinBody

Write-Host "  Join response id: $($joinResp.id)"

# Verify user 2 now has the household
$user2After = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS2

if ($user2After.households.Count -ge 1 -and $user2After.households[0].id -eq $HID) {
    Assert-Pass "User 2 joined — verify shows household"
} else {
    Assert-Fail "Expected household $HID for user 2, got: $($user2After.households | ConvertTo-Json -Compress)"
}
Write-Host ""

# =============================================================================
# Test 8: Invalid invite code returns error in expected shape
# =============================================================================
Write-Host "=== Test 8: Invalid invite code returns 404 with { detail } ==="
Write-Host "  Expected: 404 with detail message (matches mobile's ApiError)"
Write-Host "  Maps to: Error handling in onboarding"

try {
    $badJoinBody = @{ invite_code = "INVALID99" } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BASE/households/join" `
        -Method POST -Headers $HEADERS2 -Body $badJoinBody
    Assert-Fail "Should have returned error for invalid invite code"
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    $errorBody = $_.ErrorDetails.Message | ConvertFrom-Json

    Write-Host "  Status: $statusCode"
    Write-Host "  Body: $($errorBody | ConvertTo-Json -Compress)"

    if ($statusCode -ge 400 -and $null -ne $errorBody.detail) {
        Assert-Pass "Error response has { detail } field — matches mobile ApiError"
    } else {
        Assert-Fail "Error shape unexpected: status=$statusCode, hasDetail=$($null -ne $errorBody.detail)"
    }
}
Write-Host ""

# =============================================================================
# Test 9: Verify household response shape matches mobile's types
# =============================================================================
Write-Host "=== Test 9: Household response matches mobile type expectations ==="
Write-Host "  Expected: { id, name, type, invite_code, subscription_tier, members[], settings }"

$householdDetail = Invoke-RestMethod -Uri "$BASE/households/$HID" `
    -Method GET -Headers $HEADERS

$hasType = [bool]$householdDetail.type
$hasTier = [bool]$householdDetail.subscription_tier
$hasMembers = $null -ne $householdDetail.members -and $householdDetail.members.Count -ge 1
$hasSettings = $null -ne $householdDetail.settings

Write-Host "  type: $($householdDetail.type)"
Write-Host "  subscription_tier: $($householdDetail.subscription_tier)"
Write-Host "  members: $($householdDetail.members.Count)"
Write-Host "  settings.enabled_modules: $($householdDetail.settings.enabled_modules -join ', ')"

if ($hasType -and $hasTier -and $hasMembers -and $hasSettings) {
    Assert-Pass "Household response has all fields mobile expects"
} else {
    Assert-Fail "Missing: type=$hasType, tier=$hasTier, members=$hasMembers, settings=$hasSettings"
}
Write-Host ""

# =============================================================================
# Test 10: Verify response includes role for auth guard logic
# =============================================================================
Write-Host "=== Test 10: Verify response includes member role ==="
Write-Host "  Expected: households[].role field present (used by mobile for admin checks)"

$verifyWithHousehold = Invoke-RestMethod -Uri "$BASE/auth/verify" -Method POST -Headers $HEADERS

$firstHousehold = $verifyWithHousehold.households[0]
$hasRole = [bool]$firstHousehold.role

Write-Host "  Role: $($firstHousehold.role)"

if ($hasRole -and $firstHousehold.role -eq "admin") {
    Assert-Pass "Role field present — creator is admin"
} else {
    Assert-Fail "Expected role=admin, got: $($firstHousehold.role)"
}
Write-Host ""

# =============================================================================
# Cleanup
# =============================================================================
Write-Host "=== Cleanup ==="

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/leave" -Method POST -Headers $HEADERS2 | Out-Null
    Write-Host "  User 2 left household"
} catch { Write-Host "  (User 2 leave: $($_.Exception.Message))" }

try {
    Invoke-RestMethod -Uri "$BASE/households/$HID/leave" -Method POST -Headers $HEADERS | Out-Null
    Write-Host "  User 1 left household"
} catch { Write-Host "  (User 1 leave: $($_.Exception.Message))" }

Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "============================================================"
Write-Host "  Phase 9 — Mobile Auth Contract Smoke Test Results"
Write-Host "============================================================"
Write-Host ""
Write-Host "  Passed: $passed" -ForegroundColor $(if ($passed -gt 0) { "Green" } else { "White" })
Write-Host "  Failed: $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "White" })
Write-Host ""
Write-Host "  Success Criteria Coverage:"
Write-Host "  [$(if($failed -eq 0){'x'}else{' '})] API calls include valid auth token (Tests 1, 4, 5, 6)"
Write-Host "  [$(if($failed -eq 0){'x'}else{' '})] Unauthenticated users see login screen (Tests 2, 3)"
Write-Host "  [$(if($failed -eq 0){'x'}else{' '})] Onboarding create/join flow works (Tests 5, 7)"
Write-Host "  [$(if($failed -eq 0){'x'}else{' '})] API error shape matches mobile client (Test 8)"
Write-Host "  [$(if($failed -eq 0){'x'}else{' '})] Response shapes match mobile TypeScript types (Tests 9, 10)"
Write-Host ""
Write-Host "  NOTE: Google/Apple sign-in and auth persistence require device testing."
Write-Host "        This script validates the API contract the mobile app relies on."
Write-Host ""

if ($failed -gt 0) { exit 1 }
