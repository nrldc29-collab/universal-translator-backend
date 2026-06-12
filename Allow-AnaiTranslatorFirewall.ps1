# Run this script in an elevated (Administrator) PowerShell window once.
# Opens inbound TCP for the translation backend and Expo Metro so phones can connect.

param(
    [int]$BackendPort = 8000,
    [int]$ExpoPort = 8082,
    [int]$HttpsPort = 8443
)

$ErrorActionPreference = "Stop"

function Get-PortRuleName {
    param([string]$BaseName, [int]$Port)
    return "$BaseName TCP $Port"
}

function Add-FirewallRuleNetsh {
    param([string]$Name, [int]$Port)
    $existing = netsh advfirewall firewall show rule name="$Name" 2>$null
    if ($LASTEXITCODE -eq 0 -and $existing -match "Rule Name") {
        Write-Output "Firewall rule already exists (netsh): $Name"
        return
    }
    netsh advfirewall firewall add rule `
        name="$Name" `
        dir=in action=allow protocol=TCP localport=$Port `
        profile=any enable=yes | Out-Null
    Write-Output "Added firewall rule (netsh): $Name (TCP $Port)"
}

function Add-FirewallRuleCmdlet {
    param([string]$Name, [int]$Port)
    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Enable-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue | Out-Null
        Write-Output "Firewall rule already exists: $Name"
        return
    }
    New-NetFirewallRule `
        -DisplayName $Name `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $Port `
        -Action Allow `
        -Profile Any `
        -Enabled True | Out-Null
    Write-Output "Added firewall rule: $Name (TCP $Port)"
}

function Ensure-PortFirewallRule {
    param([string]$BaseName, [int]$Port)
    $name = Get-PortRuleName -BaseName $BaseName -Port $Port
    try {
        Add-FirewallRuleCmdlet -Name $name -Port $Port
    } catch {
        Write-Warning "Cmdlet firewall rule failed for ${name}: $($_.Exception.Message)"
        Add-FirewallRuleNetsh -Name $name -Port $Port
    }
}

$metroPorts = @($ExpoPort, 8081, 8082) | Select-Object -Unique
foreach ($port in $metroPorts) {
    Ensure-PortFirewallRule -BaseName "Anai Translator Expo Metro" -Port $port
}
foreach ($rule in @(
    @{ Base = "Anai Translator Backend"; Port = $BackendPort },
    @{ Base = "Anai Translator Backend HTTPS"; Port = $HttpsPort }
)) {
    Ensure-PortFirewallRule -BaseName $rule.Base -Port $rule.Port
}

try {
    $profiles = Get-NetConnectionProfile -ErrorAction SilentlyContinue |
        Where-Object { $_.NetworkCategory -eq "Public" }
    foreach ($profile in $profiles) {
        Set-NetConnectionProfile -InterfaceIndex $profile.InterfaceIndex -NetworkCategory Private
        Write-Output "Set network '$($profile.Name)' ($($profile.InterfaceAlias)) to Private (required for phone LAN access)."
    }
} catch {
    Write-Warning "Could not set Wi-Fi to Private network: $($_.Exception.Message)"
}

try {
    $nodePath = (Get-Command node -ErrorAction Stop).Source
    $nodeRule = "Anai Translator Node.js (Metro)"
    $existingNode = Get-NetFirewallRule -DisplayName $nodeRule -ErrorAction SilentlyContinue
    if (-not $existingNode) {
        New-NetFirewallRule `
            -DisplayName $nodeRule `
            -Direction Inbound `
            -Program $nodePath `
            -Action Allow `
            -Profile Any `
            -Enabled True | Out-Null
        Write-Output "Added firewall rule for Node.js: $nodePath"
    } else {
        Enable-NetFirewallRule -DisplayName $nodeRule -ErrorAction SilentlyContinue | Out-Null
        Write-Output "Firewall rule already exists: $nodeRule"
    }
} catch {
    Write-Warning "Could not add Node.js firewall rule: $($_.Exception.Message)"
}

Write-Output "Done. Phones on the same Wi-Fi can reach ports $BackendPort, $($metroPorts -join '/'), and $HttpsPort."
Write-Output "On iPhone: Settings > Expo Go > Local Network must be ON."
