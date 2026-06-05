<#
.SYNOPSIS
    Verify a Firebase token against the Hausly API and return user data.
.PARAMETER Token
    The Firebase ID token (Bearer token). If omitted, prompts for input.
.PARAMETER BaseUrl
    The API base URL. Defaults to http://localhost:8000.
#>

param(
    [string]$Token,
    [string]$BaseUrl = "http://localhost:8000"
)

if (-not $Token) {
    $Token = Read-Host "Bearer token"
}

$headers = @{
    Authorization  = "Bearer $Token"
    "Content-Type" = "application/json"
}

try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/verify" -Method POST -Headers $headers

    Write-Host "`n--- User Profile ---" -ForegroundColor Green
    Write-Host "User ID:      $($response.user_id)"
    Write-Host "Display Name: $($response.display_name)"
    Write-Host "Email:        $($response.email)"
    Write-Host "Avatar:       $($response.avatar_url ?? '(none)')"

    if ($response.households.Count -gt 0) {
        Write-Host "`n--- Households ---" -ForegroundColor Cyan
        foreach ($h in $response.households) {
            Write-Host "  [$($h.role)] $($h.name) (id: $($h.id))"
        }
    } else {
        Write-Host "`nNo active household membership." -ForegroundColor Yellow
    }
}
catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Error "401 Unauthorized — token is invalid or expired."
    } else {
        Write-Error "Request failed: $_"
    }
}
