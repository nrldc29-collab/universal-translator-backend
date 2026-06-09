# Run this script in an elevated (Administrator) PowerShell window once.
# Opens inbound TCP for the translation backend and Expo Metro so phones can connect.

param(
    [int]$BackendPort = 8000,
    [int]$ExpoPort = 8081
)

$ErrorActionPreference = "Stop"

$rules = @(
    @{ Name = "Anai Translator Expo Metro"; Port = $ExpoPort },
    @{ Name = "Anai Translator Backend"; Port = $BackendPort }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Output "Firewall rule already exists: $($rule.Name)"
        continue
    }
    New-NetFirewallRule `
        -DisplayName $rule.Name `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $rule.Port `
        -Action Allow `
        -Profile Any | Out-Null
    Write-Output "Added firewall rule: $($rule.Name) (TCP $($rule.Port))"
}

Write-Output "Done. Phones on the same Wi-Fi can reach ports $BackendPort and $ExpoPort."
