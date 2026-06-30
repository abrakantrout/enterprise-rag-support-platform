$BASE = "http://localhost:8000/api/v1"
$OK = 0
$FAIL = 0

Write-Host "=== STEP 1: Health Check ==="
$h = Invoke-RestMethod -Uri "http://localhost:8000/health"
$hs = $h.status
$hdb = $h.database
$hch = $h.chromadb
$hv = $h.version
Write-Host "status=$hs db=$hdb chroma=$hch ver=$hv"
if ($h.status -eq "healthy") { $OK++ } else { $FAIL++ }

Write-Host "=== STEP 2: Admin Login (OAuth2 form) ==="
# Login uses OAuth2PasswordRequestForm: x-www-form-urlencoded with 'username' field
$formBody = "username=admin@enterprise.com&password=SecurePassword123"
try {
    $login = Invoke-RestMethod -Uri "$BASE/auth/login" -Method Post -Body $formBody -ContentType "application/x-www-form-urlencoded"
    $TOKEN = $login.access_token
    Write-Host "Login OK - token_type=$($login.token_type)"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "Login FAILED: $msg"
    # Try to get more detail
    try {
        $resp = $_.Exception.Response
        if ($resp) {
            $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
            $body = $reader.ReadToEnd()
            Write-Host "Response body: $body"
        }
    } catch {}
    $FAIL++
    $TOKEN = $null
}

if (-not $TOKEN) {
    Write-Host "No token - stopping."
    exit 1
}

$H = @{ Authorization = "Bearer $TOKEN" }

Write-Host "=== STEP 3: GET /auth/me ==="
try {
    $me = Invoke-RestMethod -Uri "$BASE/auth/me" -Method Get -Headers $H
    $meRole = $me.role
    $meEmail = $me.email
    Write-Host "Profile OK - email=$meEmail role=$meRole"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "Profile WARN: $msg"
    $FAIL++
}

Write-Host "=== STEP 4: Documents ==="
try {
    $docs = Invoke-RestMethod -Uri "$BASE/documents" -Method Get -Headers $H
    Write-Host "Documents endpoint OK"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "Documents WARN: $msg"
    $FAIL++
}

Write-Host "=== STEP 5: Chat Sessions ==="
try {
    $sess = Invoke-RestMethod -Uri "$BASE/chat/sessions" -Method Get -Headers $H
    $sc = $sess.Count
    Write-Host "Sessions OK - count=$sc"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "Sessions WARN: $msg"
    $FAIL++
}

Write-Host "=== STEP 6: Analytics Overview ==="
try {
    $an = Invoke-RestMethod -Uri "$BASE/analytics/overview" -Method Get -Headers $H
    $td = $an.total_documents
    $ts = $an.total_chat_sessions
    $tm = $an.total_messages
    Write-Host "Analytics OK - docs=$td sessions=$ts messages=$tm"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "Analytics WARN: $msg"
    $FAIL++
}

Write-Host "=== STEP 7: Low-Rated Answers ==="
try {
    $q = Invoke-RestMethod -Uri "$BASE/analytics/low-rated-answers" -Method Get -Headers $H
    Write-Host "Low-rated answers OK - count=$($q.Count)"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "Low-rated WARN: $msg"
    $FAIL++
}

Write-Host "=== STEP 7b: Document Status ==="
try {
    $ds = Invoke-RestMethod -Uri "$BASE/analytics/document-status" -Method Get -Headers $H
    $comp = $ds.Completed
    $proc = $ds.Processing
    $failedCount = $ds.Failed
    Write-Host "Document-status OK - Completed=$comp Processing=$proc Failed=$failedCount"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "Document-status WARN: $msg"
    $FAIL++
}

Write-Host "=== STEP 8: OpenAPI Spec ==="
try {
    $oa = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json"
    $rc = $oa.paths.PSObject.Properties.Count
    $title = $oa.info.title
    Write-Host "OpenAPI OK - routes=$rc title=$title"
    $OK++
} catch {
    $msg = $_.Exception.Message
    Write-Host "OpenAPI WARN: $msg"
    $FAIL++
}

Write-Host ""
Write-Host "=== RESULT: PASS=$OK FAIL=$FAIL ==="
if ($FAIL -eq 0) {
    Write-Host "STATUS: DEMO READY"
} else {
    Write-Host "STATUS: ISSUES FOUND"
}
