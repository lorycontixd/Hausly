<#
.SYNOPSIS
    Login to Firebase with email/password and get an ID token for API testing.
.DESCRIPTION
    Prompts for email and password, authenticates against Firebase Auth REST API,
    and outputs the ID token ready to use as a Bearer token.
#>

param(
    [string]$ApiKey
)

# Try to load API key from mobile .env if not provided
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

$email = Read-Host "Email"
$password = Read-Host "Password" -AsSecureString
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

$body = @{
    email             = $email
    password          = $plainPassword
    returnSecureToken = $true
} | ConvertTo-Json

$uri = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$ApiKey"

try {
    $response = Invoke-RestMethod -Uri $uri -Method POST -Body $body -ContentType "application/json"

    Write-Host "`n--- Login Successful ---" -ForegroundColor Green
    Write-Host "Email: $($response.email)"
    Write-Host "UID:   $($response.localId)"
    Write-Host "Expires in: $($response.expiresIn)s"
    Write-Host "`n--- Token (copy below) ---" -ForegroundColor Cyan
    Write-Host $response.idToken
    Write-Host "`n--- Quick test command ---" -ForegroundColor Yellow
    Write-Host "`$token = `"$($response.idToken)`""
    Write-Host "`$headers = @{Authorization = `"Bearer `$token`"; `"Content-Type`" = `"application/json`"}"
    Write-Host "Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/verify -Method POST -Headers `$headers"
}
catch {
    $err = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Error "Firebase error: $($err.error.message)"
}
