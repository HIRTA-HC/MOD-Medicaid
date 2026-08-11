# Run this after 'cdk deploy -c env=dev' to upload React assets and invalidate CloudFront.
# Usage: .\deploy_frontend.ps1 [-Env dev] [-Version v1]

param(
    [string]$Env     = "dev",
    [string]$Version = "v1"
)

$BucketName  = "medicaid-$Env-middlewarefrontend-$Version"
$DistComment = "Medicaid_${Env}_Frontend_${Version}"

Write-Host "Building React app..."
Set-Location middleware
npm run build
Set-Location ..

Write-Host "Syncing to s3://$BucketName ..."
aws s3 sync middleware/dist/ "s3://$BucketName/" --delete --cache-control "no-cache, no-store, must-revalidate"
if ($LASTEXITCODE -ne 0) { Write-Error "S3 sync failed"; exit 1 }

Write-Host "Looking up CloudFront distribution..."
$DistId = aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='$DistComment'].Id" --output text
if (-not $DistId) { Write-Error "CloudFront distribution '$DistComment' not found"; exit 1 }

Write-Host "Invalidating CloudFront distribution $DistId ..."
aws cloudfront create-invalidation --distribution-id $DistId --paths "/*"

Write-Host "Done. Frontend is live."
