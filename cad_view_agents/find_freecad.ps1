# Helper script to find FreeCAD installation on Windows
Write-Host "Searching for FreeCAD installation..." -ForegroundColor Cyan

$found = $false

# Check common installation paths
$paths = @(
    "C:\Program Files\FreeCAD\bin\FreeCADCmd.exe",
    "C:\Program Files (x86)\FreeCAD\bin\FreeCADCmd.exe",
    "$env:LOCALAPPDATA\Programs\FreeCAD\bin\FreeCADCmd.exe",
    "$env:ProgramFiles\FreeCAD\bin\FreeCADCmd.exe",
    "$env:ProgramFiles(x86)\FreeCAD\bin\FreeCADCmd.exe"
)

Write-Host "`nChecking standard paths..." -ForegroundColor Yellow
foreach ($path in $paths) {
    if (Test-Path $path) {
        Write-Host "  [FOUND] $path" -ForegroundColor Green
        $found = $true
        Write-Host "`nTo use this installation, run:" -ForegroundColor Cyan
        Write-Host "  `$env:FREECAD_CMD = '$path'" -ForegroundColor White
        Write-Host "`nOr add to .env file in cad_view_agents directory:" -ForegroundColor Cyan
        Write-Host "  FREECAD_CMD=$path" -ForegroundColor White
    }
}

# Search in Program Files
Write-Host "`nSearching in Program Files..." -ForegroundColor Yellow
$programFiles = @("C:\Program Files", "C:\Program Files (x86)")
foreach ($pf in $programFiles) {
    if (Test-Path $pf) {
        $freecadDirs = Get-ChildItem -Path $pf -Filter "*FreeCAD*" -Directory -ErrorAction SilentlyContinue
        foreach ($dir in $freecadDirs) {
            $cmdPath = Join-Path $dir.FullName "bin\FreeCADCmd.exe"
            if (Test-Path $cmdPath) {
                Write-Host "  [FOUND] $cmdPath" -ForegroundColor Green
                $found = $true
                Write-Host "`nTo use this installation, run:" -ForegroundColor Cyan
                Write-Host "  `$env:FREECAD_CMD = '$cmdPath'" -ForegroundColor White
            }
        }
    }
}

# Check if FreeCAD is in PATH
Write-Host "`nChecking PATH..." -ForegroundColor Yellow
$pathDirs = $env:PATH -split ';'
foreach ($dir in $pathDirs) {
    $cmdPath = Join-Path $dir "FreeCADCmd.exe"
    if (Test-Path $cmdPath) {
        Write-Host "  [FOUND in PATH] $cmdPath" -ForegroundColor Green
        $found = $true
    }
}

if (-not $found) {
    Write-Host "`nFreeCAD not found in standard locations." -ForegroundColor Red
    Write-Host "`nPlease provide the path to FreeCADCmd.exe manually." -ForegroundColor Yellow
    Write-Host "Common locations:" -ForegroundColor Yellow
    Write-Host "  - C:\Program Files\FreeCAD\bin\FreeCADCmd.exe" -ForegroundColor White
    Write-Host "  - C:\Program Files (x86)\FreeCAD\bin\FreeCADCmd.exe" -ForegroundColor White
    Write-Host "  - Wherever you installed FreeCAD\bin\FreeCADCmd.exe" -ForegroundColor White
    Write-Host "`nOnce you have the path, set it with:" -ForegroundColor Cyan
    Write-Host "  `$env:FREECAD_CMD = 'C:\path\to\FreeCAD\bin\FreeCADCmd.exe'" -ForegroundColor White
}
