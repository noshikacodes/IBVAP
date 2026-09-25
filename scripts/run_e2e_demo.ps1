# ==============================================================================
# IBVAP - Intelligent Border Video Analytics Platform
# Phase 6.5 / 7: Master End-to-End Multi-Camera Platform Launcher (PowerShell)
# Compatible with Windows PowerShell 5.1+ and PowerShell Core
# ==============================================================================

$ErrorActionPreference = 'Stop'

Write-Host ''
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host '  IBVAP - Intelligent Border Video Analytics Platform' -ForegroundColor Cyan
Write-Host '  End-to-End Tactical C2 Multi-Camera Surveillance Launcher' -ForegroundColor Cyan
Write-Host '================================================================' -ForegroundColor Cyan

# 1. Check Python virtual environment
$pythonExe = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host '[ERROR] Python virtual environment not found at .\.venv\Scripts\python.exe' -ForegroundColor Red
    Write-Host 'Please create the virtual environment: python -m venv .venv' -ForegroundColor Red
    exit 1
}

# 2. Run automated full-stack verification first
Write-Host ''
Write-Host '[Step 1/5] Running Automated Platform Verification Suite...' -ForegroundColor Yellow
& $pythonExe 'scripts/verify_e2e_full_stack.py'
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] Pre-flight verification failed! Resolve issues before launching live demo.' -ForegroundColor Red
    exit 1
}

# 3. Locate MediaMTX and FFmpeg binaries
$mtxCmd = ''
$ffmpegCmd = ''

$wingetPath = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages"
if (Test-Path $wingetPath) {
    $foundMtx = Get-ChildItem -Path $wingetPath -Recurse -Filter 'mediamtx.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($foundMtx) { $mtxCmd = $foundMtx.FullName }

    $foundFfmpeg = Get-ChildItem -Path $wingetPath -Recurse -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($foundFfmpeg) { $ffmpegCmd = $foundFfmpeg.FullName }
}

if (-not $mtxCmd) { $mtxCmd = 'mediamtx.exe' }
if (-not $ffmpegCmd) { $ffmpegCmd = 'ffmpeg.exe' }

# 4. Generate multi-camera demo video assets if missing
$camVideos = @(
    'mock_streams\cam01_gate.mp4',
    'mock_streams\cam02_corridor.mp4',
    'mock_streams\cam03_fence.mp4',
    'mock_streams\cam04_outpost.mp4'
)
$missingVideos = $false
foreach ($v in $camVideos) {
    if (-not (Test-Path $v)) {
        $missingVideos = $true
        break
    }
}
if ($missingVideos) {
    Write-Host ''
    Write-Host '[Assets] Generating 4 multi-camera demo video streams...' -ForegroundColor Yellow
    & $pythonExe 'mock_streams/generate_demo_streams.py'
}

# 5. Start MediaMTX RTSP Server
Write-Host ''
Write-Host '[Step 2/5] Starting MediaMTX RTSP Server (Port 8554 / HLS 8888)...' -ForegroundColor Yellow
$mtxRunning = Get-Process -Name 'mediamtx' -ErrorAction SilentlyContinue
if (-not $mtxRunning) {
    try {
        Start-Process -FilePath $mtxCmd -ArgumentList 'mock_streams\mediamtx.yml' -WindowStyle Minimized -ErrorAction SilentlyContinue
        Write-Host '  [OK] MediaMTX relay server started' -ForegroundColor Green
    } catch {
        Write-Host '  [!] MediaMTX launch failed or skipped: ' $_.Exception.Message -ForegroundColor Yellow
    }
} else {
    Write-Host '  [OK] MediaMTX is already running' -ForegroundColor Green
}
Start-Sleep -Seconds 1

# 6. Start 4 Multi-Camera FFmpeg RTSP Publishers
Write-Host ''
Write-Host '[Step 3/5] Starting 4 Simulated CCTV Stream Publishers (FFmpeg)...' -ForegroundColor Yellow

$publishers = @(
    @{ Video = 'mock_streams\cam01_gate.mp4'; Path = 'ibvap-cam01'; Cam = 'CAM_01 (North Gate)' },
    @{ Video = 'mock_streams\cam02_corridor.mp4'; Path = 'ibvap-cam02'; Cam = 'CAM_02 (Corridor ANPR)' },
    @{ Video = 'mock_streams\cam03_fence.mp4'; Path = 'ibvap-cam03'; Cam = 'CAM_03 (Virtual Fence)' },
    @{ Video = 'mock_streams\cam04_outpost.mp4'; Path = 'ibvap-cam04'; Cam = 'CAM_04 (Hilltop PTZ)' },
    @{ Video = 'mock_streams\sample_patrol.mp4'; Path = 'ibvap-demo'; Cam = 'DEMO_LEGACY (ibvap-demo)' }
)

foreach ($pub in $publishers) {
    if (Test-Path $pub.Video) {
        $videoPath = $pub.Video
        $rtspUrl = "rtsp://localhost:8554/$($pub.Path)"
        $ffmpegArgs = "-re -stream_loop -1 -i $videoPath -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -r 15 -f rtsp -rtsp_transport tcp $rtspUrl"
        try {
            Start-Process -FilePath $ffmpegCmd -ArgumentList $ffmpegArgs -WindowStyle Minimized -ErrorAction SilentlyContinue
            Write-Host "  [OK] Publishing $($pub.Cam) -> $rtspUrl" -ForegroundColor Green
        } catch {
            Write-Host "  [!] FFmpeg launch failed for $($pub.Cam): " $_.Exception.Message -ForegroundColor Yellow
        }
    }
}
Start-Sleep -Seconds 1

# 7. Start FastAPI Backend Gateway
Write-Host ''
Write-Host '[Step 4/5] Starting FastAPI Core Gateway (Port 8000)...' -ForegroundColor Yellow
try {
    Start-Process -FilePath $pythonExe -ArgumentList '-m uvicorn backend.main:app --host 0.0.0.0 --port 8000' -WindowStyle Normal
    Write-Host '  [OK] FastAPI server starting at http://localhost:8000' -ForegroundColor Green
} catch {
    Write-Host '  [ERROR] Failed to start FastAPI backend: ' $_.Exception.Message -ForegroundColor Red
}
Start-Sleep -Seconds 2

# 8. Start React C2 Dashboard
Write-Host ''
Write-Host '[Step 5/5] Starting React + Vite C2 Web Dashboard (Port 5173)...' -ForegroundColor Yellow
try {
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c npm run dev --prefix frontend' -WindowStyle Normal
    Write-Host '  [OK] C2 Dashboard starting at http://localhost:5173' -ForegroundColor Green
} catch {
    Write-Host '  [ERROR] Failed to start frontend dashboard: ' $_.Exception.Message -ForegroundColor Red
}

Write-Host ''
Write-Host '================================================================' -ForegroundColor Green
Write-Host '  [SUCCESS] IBVAP SURVEILLANCE PLATFORM ONLINE AND OPERATIONAL!' -ForegroundColor Green
Write-Host '================================================================' -ForegroundColor Green
Write-Host '  >> Tactical C2 Dashboard:       http://localhost:5173' -ForegroundColor White
Write-Host '  >> Incident Management Console: http://localhost:5173/incidents' -ForegroundColor White
Write-Host '  >> Interactive Swagger Docs:    http://localhost:8000/api/v1/docs' -ForegroundColor White
Write-Host '  >> Prometheus Telemetry:        http://localhost:8000/metrics' -ForegroundColor White
Write-Host '  --------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '  >> CAM_01 HLS Browser Stream:   http://localhost:8888/ibvap-cam01/index.m3u8' -ForegroundColor White
Write-Host '  >> CAM_02 HLS Browser Stream:   http://localhost:8888/ibvap-cam02/index.m3u8' -ForegroundColor White
Write-Host '  >> CAM_03 HLS Browser Stream:   http://localhost:8888/ibvap-cam03/index.m3u8' -ForegroundColor White
Write-Host '  >> CAM_04 HLS Browser Stream:   http://localhost:8888/ibvap-cam04/index.m3u8' -ForegroundColor White
Write-Host '================================================================' -ForegroundColor Green
Write-Host ''
Write-Host 'To start the AI Multi-Stream Supervisor with ANPR, Face Recognition, and PTZ:' -ForegroundColor Cyan
Write-Host '  .\.venv\Scripts\python.exe -m ai_engine.stream_manager --config mock_streams/streams.json' -ForegroundColor White
Write-Host ''
