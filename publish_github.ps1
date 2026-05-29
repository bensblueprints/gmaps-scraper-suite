$PAT   = 'YOUR_GITHUB_PAT_HERE'
$OWNER = 'bensblueprints'
$DOWNLOADS = 'C:\Users\ADMIN\Desktop\Scraper Downloads'

$headers = @{
    'Authorization' = "token $PAT"
    'Accept'        = 'application/vnd.github.v3+json'
    'User-Agent'    = 'PowerShell'
}

$products = @(
    @{ name='LeadScraperPro'; repo='leadscraper-pro';  exe='LeadScraperPro.exe'; desc='Professional Google Maps lead scraper' },
    @{ name='Discovery1';     repo='discovery1-leads'; exe='Discovery1.exe';     desc='Discovery1 lead generation software'   },
    @{ name='AtomicScraper';  repo='atomic-scraper';   exe='AtomicScraper.exe';  desc='AtomicScraper lead generation software' },
    @{ name='ProspectHunter'; repo='prospect-hunter';  exe='ProspectHunter.exe'; desc='ProspectHunter lead generation software'},
    @{ name='LeadsBaby';      repo='leads-baby';       exe='LeadsBaby.exe';      desc='LeadsBaby lead generation software'    },
    @{ name='LeadRipper';     repo='lead-ripper';      exe='LeadRipper.exe';     desc='LeadRipper lead generation software'   }
)

foreach ($p in $products) {
    $pname = $p.name
    $prepo = $p.repo
    $pexe  = $p.exe
    $pdesc = $p.desc

    Write-Host ""
    Write-Host "=== $pname ===" -ForegroundColor Cyan

    # 1. Create repo
    $repoJson = "{`"name`":`"$prepo`",`"description`":`"$pdesc`",`"private`":false,`"auto_init`":false}"
    try {
        $repo = Invoke-RestMethod -Uri 'https://api.github.com/user/repos' -Method Post `
            -Headers $headers -Body $repoJson -ContentType 'application/json'
        Write-Host "  [+] Repo created: $($repo.html_url)"
    } catch {
        Write-Host "  [i] Repo already exists or error, continuing"
    }

    # 2. Initial README commit
    $readmeText = "# $pname`r`n`r`nProfessional lead generation software.`r`n`r`n## Download`r`n`r`nSee the [Releases](https://github.com/$OWNER/$prepo/releases) page for the latest version.`r`n`r`nA valid license key is required to activate."
    $readmeB64  = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($readmeText))
    $fileJson   = "{`"message`":`"Initial commit`",`"content`":`"$readmeB64`"}"
    try {
        Invoke-RestMethod -Uri "https://api.github.com/repos/$OWNER/$prepo/contents/README.md" `
            -Method Put -Headers $headers -Body $fileJson -ContentType 'application/json' | Out-Null
        Write-Host "  [+] README committed"
    } catch {
        Write-Host "  [i] README already exists, skipping"
    }

    # 3. Create release
    $relJson = "{`"tag_name`":`"v1.0.0`",`"name`":`"$pname v1.0.0`",`"body`":`"Initial release. A valid license key is required to activate.\`nContact us to purchase a license.`",`"draft`":false,`"prerelease`":false}"
    $release = $null
    try {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$OWNER/$prepo/releases" `
            -Method Post -Headers $headers -Body $relJson -ContentType 'application/json'
        Write-Host "  [+] Release v1.0.0 created (id=$($release.id))"
    } catch {
        try {
            $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$OWNER/$prepo/releases/tags/v1.0.0" `
                -Headers $headers
            Write-Host "  [i] Release already exists (id=$($release.id))"
        } catch {
            Write-Host "  [!] Could not create/fetch release: $_"
            continue
        }
    }

    # 4. Upload EXE
    $exePath = Join-Path $DOWNLOADS $pexe
    if (-not (Test-Path $exePath)) {
        Write-Host "  [!] EXE not found: $exePath"
        continue
    }
    $uploadHeaders = @{
        'Authorization' = "token $PAT"
        'Content-Type'  = 'application/octet-stream'
        'User-Agent'    = 'PowerShell'
    }
    $uploadUrl = "https://uploads.github.com/repos/$OWNER/$prepo/releases/$($release.id)/assets?name=$pexe"
    $mb = [math]::Round((Get-Item $exePath).Length / 1MB, 0)
    Write-Host "  [~] Uploading $pexe ($mb MB)..."
    try {
        $bytes = [System.IO.File]::ReadAllBytes($exePath)
        $asset = Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers $uploadHeaders -Body $bytes -TimeoutSec 300
        Write-Host "  [+] $($asset.browser_download_url)" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Upload error: $_"
    }
}

Write-Host ""
Write-Host "All done." -ForegroundColor Cyan
