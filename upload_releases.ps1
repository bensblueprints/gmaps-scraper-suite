$PAT       = 'YOUR_GITHUB_PAT_HERE'
$OWNER     = 'bensblueprints'
$DOWNLOADS = 'C:\Users\ADMIN\Desktop\Scraper Downloads'

$apiHeaders = @{
    'Authorization' = "token $PAT"
    'Accept'        = 'application/vnd.github.v3+json'
    'User-Agent'    = 'PowerShell'
}

$products = @(
    @{ name='LeadScraperPro'; repo='leadscraper-pro';  exe='LeadScraperPro.exe' },
    @{ name='Discovery1';     repo='discovery1-leads'; exe='Discovery1.exe'     },
    @{ name='AtomicScraper';  repo='atomic-scraper';   exe='AtomicScraper.exe'  },
    @{ name='ProspectHunter'; repo='prospect-hunter';  exe='ProspectHunter.exe' },
    @{ name='LeadsBaby';      repo='leads-baby';       exe='LeadsBaby.exe'      },
    @{ name='LeadRipper';     repo='lead-ripper';      exe='LeadRipper.exe'     }
)

foreach ($p in $products) {
    Write-Host "`n=== $($p.name) ===" -ForegroundColor Cyan

    # Get or create release
    $release = $null
    try {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$OWNER/$($p.repo)/releases/tags/v1.0.0" -Headers $apiHeaders
        Write-Host "  [i] Release exists (id=$($release.id))"
    } catch {
        $relBody = @{
            tag_name   = 'v1.0.0'
            name       = "$($p.name) v1.0.0"
            body       = "Initial release. A valid license key is required to activate."
            draft      = $false
            prerelease = $false
        } | ConvertTo-Json
        try {
            $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$OWNER/$($p.repo)/releases" `
                -Method Post -Headers $apiHeaders -Body $relBody -ContentType 'application/json'
            Write-Host "  [+] Release created (id=$($release.id))"
        } catch {
            Write-Host "  [!] Release error: $($_.ErrorDetails.Message)"
            continue
        }
    }

    # Check if asset already uploaded
    $assets = $release.assets | Where-Object { $_.name -eq $p.exe }
    if ($assets) {
        Write-Host "  [i] Asset already uploaded: $($assets.browser_download_url)" -ForegroundColor Green
        continue
    }

    # Upload EXE
    $exePath = Join-Path $DOWNLOADS $p.exe
    if (-not (Test-Path $exePath)) { Write-Host "  [!] EXE not found"; continue }

    $uploadUrl = "https://uploads.github.com/repos/$OWNER/$($p.repo)/releases/$($release.id)/assets?name=$($p.exe)"
    $mb = [math]::Round((Get-Item $exePath).Length / 1MB, 0)
    Write-Host "  [~] Uploading $($p.exe) ($mb MB)..."

    $uploadHeaders = @{
        'Authorization' = "token $PAT"
        'Content-Type'  = 'application/octet-stream'
        'User-Agent'    = 'PowerShell'
    }

    try {
        $bytes = [System.IO.File]::ReadAllBytes($exePath)
        $asset = Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers $uploadHeaders -Body $bytes -TimeoutSec 300
        Write-Host "  [+] $($asset.browser_download_url)" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Upload error: $($_.ErrorDetails.Message)"
    }
}

Write-Host "`nAll done." -ForegroundColor Cyan
