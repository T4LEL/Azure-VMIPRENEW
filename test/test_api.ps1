# Test script for VM IP Change API using PowerShell

param(
    [string]$BaseUrl = "https://vmsipchange-api.azurewebsites.net",
    [string]$FunctionKey = "gkDMyNS5tubtgkU8EFgrJShdS7Sij-Kosadasd-g==",
    [string]$CurrentIP = "74.225.218.206"
)

# Function to print colored output
function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Failure {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

Write-Host "Testing VM IP Change API" -ForegroundColor Green
Write-Host "Base URL: $BaseUrl"
Write-Host "Current IP: $CurrentIP"
Write-Host "Function Key: $(if ($FunctionKey) { 'provided' } else { 'not provided' })"
Write-Host "----------------------------------------"

# Test health endpoint
Write-Info "`nTesting health endpoint..."

$healthUrl = "$BaseUrl/api/health"
if ($FunctionKey) {
    $healthUrl += "?code=$FunctionKey"
}

try {
    $healthResponse = Invoke-RestMethod -Uri $healthUrl -Method Get -ErrorAction Stop
    Write-Success "Health check passed"
    Write-Host "Response: $($healthResponse | ConvertTo-Json -Compress)"
}
catch {
    Write-Failure "Health check failed"
    Write-Host "Error: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status: $statusCode"
    }
}

# Test IP change endpoint
Write-Info "`nTesting IP change endpoint..."

$changeUrl = "$BaseUrl/api/change-vm-ip"
if ($FunctionKey) {
    $changeUrl += "?code=$FunctionKey"
}

$requestBody = @{
    current_ip = $CurrentIP
}

Write-Host "Request: $($requestBody | ConvertTo-Json -Compress)"

try {
    $changeResponse = Invoke-RestMethod -Uri $changeUrl -Method Post -Body ($requestBody | ConvertTo-Json) -ContentType "application/json" -ErrorAction Stop
    Write-Success "IP change request successful"
    Write-Host "Response: $($changeResponse | ConvertTo-Json -Depth 3)"
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "HTTP Status: $statusCode"
    
    if ($statusCode -eq 404) {
        Write-Warning "VM not found or access denied"
    }
    else {
        Write-Failure "IP change request failed"
    }
    
    Write-Host "Error: $($_.Exception.Message)"
    
    # Try to get error response body
    if ($_.Exception.Response) {
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $errorBody = $reader.ReadToEnd()
            $reader.Close()
            $stream.Close()
            
            if ($errorBody) {
                Write-Host "Response: $errorBody"
            }
        }
        catch {
            # Ignore errors when trying to read error response
        }
    }
}

Write-Host "`nTest completed!" -ForegroundColor Green
