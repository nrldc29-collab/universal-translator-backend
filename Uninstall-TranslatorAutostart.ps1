param(
    [string]$TaskPrefix = "AnaiTranslator"
)

$ErrorActionPreference = "Stop"

foreach ($taskName in @("$TaskPrefix-Start", "$TaskPrefix-Monitor")) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Output "Removed $taskName"
    } else {
        Write-Output "Not installed: $taskName"
    }
}

$startupFolder = [Environment]::GetFolderPath("Startup")
foreach ($fileName in @("$TaskPrefix-Start.cmd", "$TaskPrefix-Monitor.cmd")) {
    $path = Join-Path $startupFolder $fileName
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
        Write-Output "Removed $path"
    } else {
        Write-Output "Not installed: $path"
    }
}
