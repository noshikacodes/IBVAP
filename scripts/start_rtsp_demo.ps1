# IBVAP - Automated RTSP Development & Verification Script
# Launches MediaMTX, RTSP Publisher, FastAPI Backend, React Dashboard & AI Vision Ingestion

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  IBVAP - Intelligent Border Video Analytics Platform (Phase 5A)" -ForegroundColor Cyan
Write-Host "  Real-Time CCTV / RTSP Stream Ingestion Pipeline" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Resolve Executables
$mtxCmd = (Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "mediamtx.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
$ffmpegCmd = (Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName

if (-not $mtxCmd) {
    Write-Host "[INFO] Locating mediamtx in PATH..." -ForegroundColor Yellow
    $mtxCmd = "mediamtx"
}
if (-not $ffmpegCmd) {
    Write-Host "[INFO] Locating ffmpeg in PATH..." -ForegroundColor Yellow
    $ffmpegCmd = "ffmpeg"
}

Write-Host "[✓] MediaMTX Binary: $mtxCmd" -ForegroundColor Green
Write-Host "[✓] FFmpeg Binary:   $ffmpegCmd" -ForegroundColor Green

# 2. Check mock stream
$sampleVideo = "mock_streams\sample_patrol.mp4"
if (-not (Test-Path $sampleVideo)) {
    Write-Host "[ERROR] Sample video not found: $sampleVideo" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/4] Starting MediaMTX RTSP Relay Server (:8554)..." -ForegroundColor Yellow
Start-Process -FilePath $mtxCmd -ArgumentList "mock_streams\mediamtx.yml" -WindowStyle Minimized

Start-Sleep -Seconds 2

Write-Host "[2/4] Starting FFmpeg RTSP Publisher (rtsp://localhost:8554/ibvap-demo)..." -ForegroundColor Yellow
Start-Process -FilePath $ffmpegCmd -ArgumentList "-re -stream_loop -1 -i mock_streams\sample_patrol.mp4 -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -r 15 -f rtsp -rtsp_transport tcp rtsp://localhost:8554/ibvap-demo" -WindowStyle Minimized

Start-Sleep -Seconds 2

Write-Host "[3/4] Starting FastAPI Gateway (http://localhost:8000)..." -ForegroundColor Yellow
Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000" -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "[4/4] Starting React C2 Dashboard (http://localhost:5173)..." -ForegroundColor Yellow
Start-Process -FilePath "npm" -ArgumentList "run dev --prefix frontend" -WindowStyle Normal

Write-Host "`n================================================================" -ForegroundColor Green
Write-Host "  RTSP Pipeline Services Started Successfully!" -ForegroundColor Green
Write-Host "  RTSP Stream:    rtsp://localhost:8554/ibvap-demo" -ForegroundColor White
Write-Host "  C2 Dashboard:   http://localhost:5173" -ForegroundColor White
Write-Host "  Backend API:    http://localhost:8000/api/v1/docs" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Green
Write-Host "`nTo run the AI Ingestion Worker against the live RTSP stream, execute:" -ForegroundColor Cyan
Write-Host "  .venv\Scripts\python.exe -m ai_engine.worker --input rtsp://localhost:8554/ibvap-demo --camera-id CAM_01 --tracking --spatial-rules mock_streams/spatial_rules.json" -ForegroundColor White
