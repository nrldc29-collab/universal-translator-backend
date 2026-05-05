param(
    [Parameter(Mandatory = $true)]
    [string]$SpaceId,

    [switch]$Private
)

$ErrorActionPreference = "Stop"

if (-not $env:HF_TOKEN) {
    Write-Host "HF_TOKEN is not set. Paste a Hugging Face write token when prompted."
}

python -m pip show huggingface_hub *> $null
if ($LASTEXITCODE -ne 0) {
    python -m pip install --upgrade huggingface_hub
}

$argsList = @("scripts/deploy_hf_space.py", "--space-id", $SpaceId, "--folder", "hf-space")
if ($Private) {
    $argsList += "--private"
}

python @argsList
