# Bootstrap and verify database accounts
$BASE = "http://localhost:8000/api/v1"

Write-Host "=== 1. Register First Administrator ==="
$adminPayload = @{
    email = "admin@enterprise.com"
    password = "SecurePassword123"
    first_name = "System"
    last_name = "Admin"
    role = "Administrator"
} | ConvertTo-Json

try {
    $adminReg = Invoke-RestMethod -Uri "$BASE/auth/register" -Method Post -Body $adminPayload -ContentType "application/json"
    Write-Host "Admin Registration Success: email=$($adminReg.email), role=$($adminReg.role)"
} catch {
    Write-Host "Admin Registration FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "Response details: $($reader.ReadToEnd())"
    }
}

Write-Host "`n=== 2. Admin Login ==="
$loginBody = "username=admin@enterprise.com&password=SecurePassword123"
try {
    $login = Invoke-RestMethod -Uri "$BASE/auth/login" -Method Post -Body $loginBody -ContentType "application/x-www-form-urlencoded"
    $adminToken = $login.access_token
    Write-Host "Admin Login Success! Token retrieved."
} catch {
    Write-Host "Admin Login FAIL: $($_.Exception.Message)"
}

if ($adminToken) {
    $H = @{ Authorization = "Bearer $adminToken" }

    Write-Host "`n=== 3. Register Support Agent (Authenticated) ==="
    $agentPayload = @{
        email = "agent@enterprise.com"
        password = "SecurePassword123"
        first_name = "Support"
        last_name = "Agent"
        role = "Support Agent"
    } | ConvertTo-Json

    try {
        $agentReg = Invoke-RestMethod -Uri "$BASE/auth/register" -Method Post -Body $agentPayload -ContentType "application/json" -Headers $H
        Write-Host "Agent Registration Success: email=$($agentReg.email), role=$($agentReg.role)"
    } catch {
        Write-Host "Agent Registration FAIL: $($_.Exception.Message)"
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Host "Response details: $($reader.ReadToEnd())"
        }
    }

    Write-Host "`n=== 4. Verify /auth/me for Admin ==="
    try {
        $meAdmin = Invoke-RestMethod -Uri "$BASE/auth/me" -Method Get -Headers $H
        Write-Host "Verified /auth/me: email=$($meAdmin.email), role=$($meAdmin.role)"
    } catch {
        Write-Host "Verify Admin FAIL: $($_.Exception.Message)"
    }
}
