<#
.SYNOPSIS
    Login to Firebase and verify the token against the Hausly API in one step.
.PARAMETER ApiKey
    Firebase Web API key. Auto-read from apps/mobile/.env if omitted.
.PARAMETER BaseUrl
    The API base URL. Defaults to http://localhost:8000.
#>

param(
    [string]$ApiKey,
    [string]$BaseUrl = "http://localhost:8000"
)

# --- Resolve API key ---
if (-not $ApiKey) {
    $envPath = Join-Path $PSScriptRoot "..\..\mobile\.env"
    if (Test-Path $envPath) {
        $line = Get-Content $envPath | Where-Object { $_ -match "^EXPO_PUBLIC_FIREBASE_API_KEY=(.+)$" }
        if ($line -and $Matches[1]) {
            $ApiKey = $Matches[1]
        }
    }
}
if (-not $ApiKey) {
    Write-Error "Firebase API key not found. Pass -ApiKey or set EXPO_PUBLIC_FIREBASE_API_KEY in apps/mobile/.env"
    exit 1
}

# --- Credentials ---
$email = Read-Host "Email"
$password = Read-Host "Password" -AsSecureString
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

# --- Firebase login ---
Write-Host "`nAuthenticating with Firebase..." -ForegroundColor Gray

$body = @{
    email             = $email
    password          = $plainPassword
    returnSecureToken = $true
} | ConvertTo-Json

$uri = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$ApiKey"

try {
    $fbResponse = Invoke-RestMethod -Uri $uri -Method POST -Body $body -ContentType "application/json"
}
catch {
    $err = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Error "Firebase login failed: $($err.error.message)"
    exit 1
}

Write-Host "Firebase login OK (UID: $($fbResponse.localId))" -ForegroundColor Green

# --- Verify with Hausly API ---
Write-Host "Verifying with Hausly API..." -ForegroundColor Gray

$headers = @{
    Authorization  = "Bearer $($fbResponse.idToken)"
    "Content-Type" = "application/json"
}

try {
    $apiResponse = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/verify" -Method POST -Headers $headers
}
catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Error "API returned 401 — token rejected."
    } else {
        Write-Error "API request failed: $_"
    }
    exit 1
}

# --- Output ---
Write-Host "`n--- User Profile ---" -ForegroundColor Green
Write-Host "User ID:      $($apiResponse.user_id)"
Write-Host "Display Name: $($apiResponse.display_name)"
Write-Host "Email:        $($apiResponse.email)"
Write-Host "Avatar:       $($apiResponse.avatar_url ?? '(none)')"

if ($apiResponse.households.Count -gt 0) {
    Write-Host "`n--- Households ---" -ForegroundColor Cyan
    foreach ($h in $apiResponse.households) {
        Write-Host "  [$($h.role)] $($h.name) (id: $($h.id))"
    }
} else {
    Write-Host "`nNo active household membership." -ForegroundColor Yellow
}

Write-Host "`n--- Token (expires in $($fbResponse.expiresIn)s) ---" -ForegroundColor Cyan
Write-Host $fbResponse.idToken
