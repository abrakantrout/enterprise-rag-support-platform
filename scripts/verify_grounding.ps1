# Create test document with all necessary facts
$txt = @"
Refund Policy: Customers can request refunds within 14 days of purchase.
Warranty Policy: Water damage is not covered under the standard warranty.
Shipping Policy: Standard shipping takes 3-7 business days.
"@

$filePath = "uploads/temp_grounding_test.txt"
[System.IO.File]::WriteAllText($filePath, $txt)

# PowerShell verification of the 4 questions
$BASE = "http://localhost:8000/api/v1"
$formBody = "username=admin@enterprise.com&password=SecurePassword123"
$login = Invoke-RestMethod -Uri "$BASE/auth/login" -Method Post -Body $formBody -ContentType "application/x-www-form-urlencoded"
$tok = $login.access_token
$H = @{ Authorization = "Bearer $tok" }

Write-Host "=== 1. Uploading Grounding Test Document ==="
$content = [System.IO.File]::ReadAllBytes($filePath)
$boundary = [System.Guid]::NewGuid().ToString()
$multipartContent = "--$boundary`r`nContent-Disposition: form-data; name=`"file`"; filename=`"temp_grounding_test.txt`"`r`nContent-Type: text/plain`r`n`r`n$txt`r`n--$boundary--"
$uploadHeaders = @{ Authorization = "Bearer $tok"; "Content-Type" = "multipart/form-data; boundary=$boundary" }
$up = Invoke-RestMethod -Uri "$BASE/documents/upload" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($multipartContent)) -Headers $uploadHeaders
$docId = $up.id
Write-Host "Uploaded. ID=$docId"

Write-Host "`n=== 2. Processing Document ==="
Invoke-RestMethod -Uri "$BASE/documents/$docId/extract" -Method Post -Headers $H | Out-Null
Write-Host "Extracted."
Invoke-RestMethod -Uri "$BASE/documents/$docId/chunks" -Method Post -Headers $H | Out-Null
Write-Host "Chunked."
Invoke-RestMethod -Uri "$BASE/documents/$docId/embeddings" -Method Post -Headers $H | Out-Null
Write-Host "Embedded."
Invoke-RestMethod -Uri "$BASE/documents/$docId/index" -Method Post -Headers $H | Out-Null
Write-Host "Indexed."

Write-Host "`n=== 3. Creating Chat Session ==="
$sessResp = Invoke-RestMethod -Uri "$BASE/chat/sessions" -Method Post -Headers $H
$sid = $sessResp.session_id
Write-Host "Session ID: $sid"

function AskQuestion($q) {
    Write-Host "`nQuery: $q" -ForegroundColor Cyan
    $body = @{ question = $q } | ConvertTo-Json
    $chatH = @{ Authorization = "Bearer $tok"; "Content-Type" = "application/json" }
    $resp = Invoke-RestMethod -Uri "$BASE/chat/sessions/$sid/answer" -Method Post -Body $qBody -Headers $chatH
    $ans = $resp.answer
    Write-Host "Answer: $ans" -ForegroundColor Green
    return $ans
}

$qBody = '{"question":"How many days do I have to request a refund?"}'
$r1 = AskQuestion "How many days do I have to request a refund?"

$qBody = '{"question":"Is water damage covered?"}'
$r2 = AskQuestion "Is water damage covered?"

$qBody = '{"question":"How long does standard shipping take?"}'
$r3 = AskQuestion "How long does standard shipping take?"

$qBody = '{"question":"Do you provide student discounts?"}'
$r4 = AskQuestion "Do you provide student discounts?"

# Clean up temp file
Remove-Item $filePath
