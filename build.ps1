# Builds a portable dist\GlanceSwitch folder (and GlanceSwitch-windows.zip).
# Usage: .\build.ps1
# PyInstaller logs to stderr; in Windows PowerShell "Stop" would abort on that.
# Failures are detected through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"

# App icon, drawn with the same code as the tray icon.
& $py -c "from glance.tray import make_icon; make_icon('ok').save('build_icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64)])"

& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name GlanceSwitch `
    --icon build_icon.ico `
    --add-data "models\face_landmarker.task;models" `
    --collect-all mediapipe `
    run_glance.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Compress-Archive -Path dist\GlanceSwitch -DestinationPath dist\GlanceSwitch-windows.zip -Force
Write-Host "Listo: dist\GlanceSwitch-windows.zip"
