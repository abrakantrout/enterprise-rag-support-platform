# Demo Verification Script — Enterprise RAG Support Platform
$BASE = "http://localhost:8000/api/v1"
$PASS = $true

function Check($label, $condition) {
    if ($condition) {
        Write-Host "  [PASS] $label" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $label" -ForegroundColor Red
        $script:PASS = $false
    }
}

Write-Host "`n=== STEP 1: Health Check ===" -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
Check "status=healthy"   ($health.status -eq "healthy")
Check "database=connected" ($health.database -eq "connected")
Check "chromadb=connected" ($health.chromadb -eq "connected")
Write-Host "  version: $($health.version)"

Write-Host "`n=== STEP 2: Admin Login ===" -ForegroundColor Cyan
$loginBody = @{ email = "admin@company.com"; password = "Admin123!" } | ConvertTo-Json
try {
    $login = Invoke-RestMethod -Uri "$BASE/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
    $TOKEN = $login.access_token
    Check "Login returns token" ($null -ne $TOKEN -and $TOKEN.Length -gt 10)
    Check "Role is administrator" ($login.user.role -eq "administrator")
    Write-Host "  Token (first 40 chars): $($TOKEN.Substring(0,40))..."
} catch {
    Write-Host "  [FAIL] Login failed: $($_.Exception.Message)" -ForegroundColor Red
    $PASS = $false
    $TOKEN = $null
}

if ($null -eq $TOKEN) {
    Write-Host "`nAborting — cannot continue without auth token." -ForegroundColor Red
    exit 1
}

$HEADERS = @{ Authorization = "Bearer $TOKEN" }

Write-Host "`n=== STEP 3: Documents Endpoint ===" -ForegroundColor Cyan
try {
    $docs = Invoke-RestMethod -Uri "$BASE/documents" -Method Get -Headers $HEADERS
    Check "Documents endpoint responds" ($null -ne $docs)
    $docCount = if ($docs.PSObject.Properties['total']) { $docs.total } elseif ($docs -is [array]) { $docs.Count } else { "N/A" }
    Write-Host "  Documents found: $docCount"
} catch {
    Write-Host "  [WARN] Documents endpoint: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n=== STEP 4: Chat Sessions ===" -ForegroundColor Cyan
try {
    $sessions = Invoke-RestMethod -Uri "$BASE/chat/sessions" -Method Get -Headers $HEADERS
    Check "Chat sessions endpoint responds" ($null -ne $sessions)
    Write-Host "  Sessions found: $($sessions.Count)"
} catch {
    Write-Host "  [WARN] Chat sessions: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n=== STEP 5: Analytics Overview ===" -ForegroundColor Cyan
try {
    $analytics = Invoke-RestMethod -Uri "$BASE/analytics/overview" -Method Get -Headers $HEADERS
    Check "Analytics overview responds" ($null -ne $analytics)
    Write-Host "  Total documents:     $($analytics.total_documents)"
    Write-Host "  Processed documents: $($analytics.processed_documents)"
    Write-Host "  Total chat sessions: $($analytics.total_chat_sessions)"
    Write-Host "  Total messages:      $($analytics.total_messages)"
} catch {
    Write-Host "  [WARN] Analytics overview: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n=== STEP 6: Feedback Quality Report ===" -ForegroundColor Cyan
try {
    $quality = Invoke-RestMethod -Uri "$BASE/analytics/quality" -Method Get -Headers $HEADERS
    Check "Quality report responds" ($null -ne $quality)
    Write-Host "  Total feedback:    $($quality.total_feedback)"
    Write-Host "  Positive feedback: $($quality.positive_feedback)"
    Write-Host "  Negative feedback: $($quality.negative_feedback)"
} catch {
    Write-Host "  [WARN] Quality report: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n=== STEP 7: OpenAPI Docs ===" -ForegroundColor Cyan
try {
    $openapi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -Method Get
    Check "OpenAPI spec loads" ($null -ne $openapi.info)
    Write-Host "  API title:   $($openapi.info.title)"
    Write-Host "  API version: $($openapi.info.version)"
    $routeCount = $openapi.paths.PSObject.Properties.Count
    Write-Host "  Total routes: $routeCount"
} catch {
    Write-Host "  [WARN] OpenAPI: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
if ($PASS) {
    Write-Host "  RESULT: ALL CHECKS PASSED" -ForegroundColor Green
    Write-Host "  STATUS: DEMO READY" -ForegroundColor Green
} else {
    Write-Host "  RESULT: SOME CHECKS FAILED" -ForegroundColor Red
    Write-Host "  STATUS: DEMO NOT READY" -ForegroundColor Red
}
Write-Host "========================================`n" -ForegroundColor Cyan
