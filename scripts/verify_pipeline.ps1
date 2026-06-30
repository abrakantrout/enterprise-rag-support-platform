$BASE = "http://localhost:8000/api/v1"
$formBody = "username=admin@enterprise.com&password=SecurePassword123"
$login = Invoke-RestMethod -Uri "$BASE/auth/login" -Method Post -Body $formBody -ContentType "application/x-www-form-urlencoded"
$tok = $login.access_token
$H = @{ Authorization = "Bearer $tok" }

Write-Host "=== 1. Health check (should be healthy) ==="
$healthResp = Invoke-RestMethod -Uri "http://localhost:8000/health"
$hs = $healthResp.status
Write-Host "status=$hs"
if ($hs -eq "healthy") { Write-Host "PASS: Health" } else { Write-Host "FAIL: Health" }

Write-Host "=== 2. Upload a fresh test document ==="
$content = [System.Text.Encoding]::UTF8.GetBytes("Customer refund policy: All refunds are processed within 5 business days. Contact support@company.com for assistance. Eligibility requires purchase within 30 days.")
$b64 = [Convert]::ToBase64String($content)
$uploadBody = @{
    visibility = "public"
}
$fileBytes = [System.IO.MemoryStream]::new($content)
$boundary = [System.Guid]::NewGuid().ToString()
$multipartContent = "--$boundary`r`nContent-Disposition: form-data; name=`"file`"; filename=`"refund_policy_test.txt`"`r`nContent-Type: text/plain`r`n`r`n" + [System.Text.Encoding]::UTF8.GetString($content) + "`r`n--$boundary--"
$uploadHeaders = @{ Authorization = "Bearer $tok"; "Content-Type" = "multipart/form-data; boundary=$boundary" }
try {
    $up = Invoke-RestMethod -Uri "$BASE/documents/upload" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($multipartContent)) -Headers $uploadHeaders
    $docId = $up.id
    Write-Host "Upload OK - id=$docId"
} catch {
    Write-Host "Upload WARN: $($_.Exception.Message) - using existing doc"
    $docs = Invoke-RestMethod -Uri "$BASE/documents?page=1&size=50" -Method Get -Headers $H
    $docId = $docs.items[0].id
    Write-Host "Using existing doc: $docId"
}

Write-Host "=== 3. Extract ==="
try {
    Invoke-RestMethod -Uri "$BASE/documents/$docId/extract" -Method Post -Headers $H | Out-Null
    Write-Host "PASS: Extract"
} catch {
    Write-Host "WARN Extract: $($_.Exception.Message)"
}

Write-Host "=== 4. Chunk ==="
try {
    Invoke-RestMethod -Uri "$BASE/documents/$docId/chunks" -Method Post -Headers $H | Out-Null
    Write-Host "PASS: Chunk"
} catch {
    Write-Host "WARN Chunk: $($_.Exception.Message)"
}

Write-Host "=== 5. Embed ==="
try {
    Invoke-RestMethod -Uri "$BASE/documents/$docId/embeddings" -Method Post -Headers $H | Out-Null
    Write-Host "PASS: Embed"
} catch {
    $msg = $_.Exception.Message
    Write-Host "FAIL Embed: $msg"
}

Write-Host "=== 6. Index ==="
try {
    Invoke-RestMethod -Uri "$BASE/documents/$docId/index" -Method Post -Headers $H | Out-Null
    Write-Host "PASS: Index"
} catch {
    $msg = $_.Exception.Message
    Write-Host "FAIL Index: $msg"
}

Write-Host "=== 7. Chat answer ==="
try {
    $sessResp = Invoke-RestMethod -Uri "$BASE/chat/sessions" -Method Post -Headers $H
    $sid = $sessResp.session_id
    Write-Host "Session created: $sid"
    $qBody = '{"question":"What is the refund policy?"}'
    $chatH = @{ Authorization = "Bearer $tok"; "Content-Type" = "application/json" }
    $ans = Invoke-RestMethod -Uri "$BASE/chat/sessions/$sid/answer" -Method Post -Body $qBody -Headers $chatH
    $ansLen = $ans.answer.Length
    Write-Host "PASS: Chat answer received (length=$ansLen chars)"
    Write-Host "Answer preview: $($ans.answer.Substring(0, [Math]::Min(120, $ansLen)))..."
} catch {
    $msg = $_.Exception.Message
    Write-Host "FAIL Chat: $msg"
}

Write-Host ""
Write-Host "=== DONE ==="
