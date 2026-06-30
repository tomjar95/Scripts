# Get all running calculator processes
$calcProcesses = Get-Process -Name Calculator, calc -ErrorAction SilentlyContinue

# Check if there are multiple calculator processes running
if ($calcProcesses.Count -gt 1) {
    Write-Host "Found $($calcProcesses.Count) calculator processes running."
    
    # Keep the first process and stop all others
    for ($i = 1; $i -lt $calcProcesses.Count; $i++) {
        try {
            $calcProcesses[$i] | Stop-Process -Force
            Write-Host "Stopped calculator process with ID: $($calcProcesses[$i].Id)"
        }
        catch {
            Write-Warning "Failed to stop calculator process with ID: $($calcProcesses[$i].Id)"
        }
    }
    Write-Host "One calculator instance remains running."
}
elseif ($calcProcesses.Count -eq 1) {
    Write-Host "Only one calculator process is running. No action needed."
}
else {
    Write-Host "No calculator processes found."
}