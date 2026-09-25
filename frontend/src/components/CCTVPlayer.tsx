import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export interface CCTVPlayerProps {
  streamUrl?: string;
  sourceType?: string;
  cameraId: string;
  cameraName?: string;
  sector?: string;
  isOnline?: boolean;
  style?: React.CSSProperties;
  showOverlay?: boolean;
  aspectRatio?: string;
}

export interface DetectionBox {
  track_id?: number;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  trajectory?: [number, number][];
}

export interface CameraTelemetry {
  camera_id: string;
  fps: number;
  active_tracks: number;
  total_unique_tracks: number;
  status: string;
  detections: DetectionBox[];
  target_classes?: string[];
  traffic?: {
    counting_line?: [[number, number], [number, number]];
    total_counted?: number;
    counted_totals?: Record<string, number>;
  };
}

const CLASS_COLOR_MAP: Record<string, string> = {
  car: '#38bdf8',        // Cyan
  truck: '#f59e0b',      // Amber
  bus: '#a855f7',        // Purple
  motorcycle: '#ec4899', // Pink
  bicycle: '#06b6d4',    // Cyan-green
  person: '#22c55e',     // Bright Green
  human: '#22c55e',      // Bright Green
};

/**
 * Resolves browser-compatible HLS playback URL from RTSP source or stream identifier.
 */
export function resolveHlsUrl(source?: string, cameraId?: string): string {
  const host = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
  const targetHost = host === 'localhost' ? '127.0.0.1' : (host || '127.0.0.1');

  // Direct HLS playlist URL
  if (source && (source.startsWith('http://') || source.startsWith('https://'))) {
    if (source.includes('.m3u8') || source.includes(':8888')) {
      return source;
    }
  }

  // Camera ID mapping for deterministic multi-camera streams
  if (cameraId) {
    const normId = cameraId.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (normId.includes('95366') || normId.includes('SEJONG') || normId.includes('1809') || normId.includes('GITS')) {
      // Backend CORS-free reverse-proxied HLS stream
      return `http://${targetHost}:8000/api/v1/cameras/${cameraId}/hls-proxy/playlist.m3u8`;
    }
    if (normId.includes('01') || normId === 'CAM01' || normId === 'CAMGATE') {
      return `http://${targetHost}:8888/ibvap-cam01/index.m3u8`;
    }
    if (normId.includes('02') || normId === 'CAM02' || normId === 'CAMPATROL') {
      return `http://${targetHost}:8888/ibvap-cam02/index.m3u8`;
    }
    if (normId.includes('03') || normId === 'CAM03' || normId === 'CAMFENCE') {
      return `http://${targetHost}:8888/ibvap-cam03/index.m3u8`;
    }
    if (normId.includes('04') || normId === 'CAM04' || normId === 'CAMOUTPOST04') {
      return `http://${targetHost}:8888/ibvap-cam04/index.m3u8`;
    }
  }

  // If RTSP URL, extract path
  if (source && source.startsWith('rtsp://')) {
    try {
      const url = new URL(source.replace('rtsp://', 'http://'));
      const streamPath = url.pathname.replace(/^\//, '');
      if (streamPath) {
        return `http://${targetHost}:8888/${streamPath}/index.m3u8`;
      }
    } catch {
      // ignore
    }
  }

  return `http://${targetHost}:8888/ibvap-cam01/index.m3u8`;
}

export const CCTVPlayer: React.FC<CCTVPlayerProps> = ({
  streamUrl,
  cameraId,
  cameraName,
  sector = 'Sector Alpha',
  isOnline = true,
  style,
  showOverlay = true,
  aspectRatio = '16/9',
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [playbackState, setPlaybackState] = useState<'connecting' | 'playing' | 'error'>('connecting');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [retryCount, setRetryCount] = useState<number>(0);
  const [activeHlsUrl, setActiveHlsUrl] = useState<string>(resolveHlsUrl(streamUrl, cameraId));
  const [telemetry, setTelemetry] = useState<CameraTelemetry | null>(null);
  const [aiOverlayEnabled, setAiOverlayEnabled] = useState<boolean>(true);

  const host = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
  const targetHost = host === 'localhost' ? '127.0.0.1' : (host || '127.0.0.1');

  // Poll real-time AI telemetry for this camera
  useEffect(() => {
    let isSubscribed = true;
    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`http://${targetHost}:8000/api/v1/cameras/${cameraId}/telemetry`);
        if (res.ok && isSubscribed) {
          const data: CameraTelemetry = await res.json();
          if (data && data.status !== 'idle') {
            setTelemetry(data);
          }
        }
      } catch {
        // Backend might be warming up
      }
    };

    fetchTelemetry();
    const timer = setInterval(fetchTelemetry, 250);
    return () => {
      isSubscribed = false;
      clearInterval(timer);
    };
  }, [cameraId, targetHost]);

  // Resolve dynamic HLS URL if needed (e.g. GITS 95366, 1809)
  useEffect(() => {
    if (streamUrl && streamUrl.includes('.m3u8')) {
      setActiveHlsUrl(streamUrl);
      return;
    }
    if (cameraId.includes('95366') || cameraId.includes('1809') || cameraId.includes('GITS') || streamUrl?.includes('95366') || streamUrl?.includes('1809') || streamUrl?.includes('gits')) {
      setActiveHlsUrl(`http://${targetHost}:8000/api/v1/cameras/${cameraId}/hls-proxy/playlist.m3u8`);
      return;
    }
    setActiveHlsUrl(resolveHlsUrl(streamUrl, cameraId));
  }, [streamUrl, cameraId, retryCount, targetHost]);

  // Native HLS Video Player lifecycle
  useEffect(() => {
    let isMounted = true;
    const video = videoRef.current;

    if (!video || !isOnline) {
      setPlaybackState('error');
      setErrorMessage('Camera stream marked offline');
      return;
    }

    setPlaybackState('connecting');

    // Cleanup any existing HLS instance
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 30,
        maxBufferLength: 5,
        maxMaxBufferLength: 10,
        manifestLoadingTimeOut: 5000,
        manifestLoadingMaxRetry: 10,
        levelLoadingTimeOut: 5000,
      });

      hlsRef.current = hls;

      hls.on(Hls.Events.MEDIA_ATTACHED, () => {
        if (!isMounted) return;
        hls.loadSource(activeHlsUrl);
      });

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        if (!isMounted) return;
        video.muted = true;
        video.defaultMuted = true;
        const playPromise = video.play();
        if (playPromise !== undefined) {
          playPromise
            .then(() => {
              if (isMounted) setPlaybackState('playing');
            })
            .catch(() => {
              video.muted = true;
              video.play().then(() => {
                if (isMounted) setPlaybackState('playing');
              }).catch((err) => {
                if (isMounted) {
                  setPlaybackState('error');
                  setErrorMessage(err.message || 'Click to start video');
                }
              });
            });
        }
      });

      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (!isMounted) return;
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              setPlaybackState('error');
              setErrorMessage('HLS stream network error — retrying connection...');
              hls.startLoad();
              setTimeout(() => {
                if (isMounted) setRetryCount((prev) => prev + 1);
              }, 3000);
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              setPlaybackState('error');
              setErrorMessage('Media decode error — recovering stream...');
              hls.recoverMediaError();
              break;
            default:
              setPlaybackState('error');
              setErrorMessage('Unrecoverable stream error');
              hls.destroy();
              setTimeout(() => {
                if (isMounted) setRetryCount((prev) => prev + 1);
              }, 4000);
              break;
          }
        }
      });

      hls.attachMedia(video);
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Native Safari / iOS HLS support
      video.src = activeHlsUrl;
      video.addEventListener('loadedmetadata', () => {
        video.play().then(() => {
          if (isMounted) setPlaybackState('playing');
        }).catch((err) => {
          if (isMounted) {
            setPlaybackState('error');
            setErrorMessage(err.message || 'Playback error');
          }
        });
      });
      video.addEventListener('error', () => {
        if (isMounted) {
          setPlaybackState('error');
          setErrorMessage('Native video load error');
        }
      });
    } else {
      setPlaybackState('error');
      setErrorMessage('HLS video playback is not supported in this browser');
    }

    return () => {
      isMounted = false;
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [activeHlsUrl, isOnline, retryCount]);

  return (
    <div
      onClick={() => {
        if (videoRef.current?.paused) {
          videoRef.current.play().then(() => setPlaybackState('playing')).catch(() => {});
        }
      }}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        aspectRatio: aspectRatio,
        backgroundColor: '#020617',
        borderRadius: '6px',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: playbackState === 'playing' ? 'default' : 'pointer',
        ...style,
      }}
    >
      {/* Real-time Smooth 30 FPS Live Video Stream */}
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        onPlay={() => setPlaybackState('playing')}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: playbackState === 'playing' ? 'block' : 'none',
        }}
      />

      {/* Standby / Connecting / Error State Overlay */}
      {playbackState !== 'playing' && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(2, 6, 23, 0.95)',
            color: '#94a3b8',
            padding: '1.25rem',
            textAlign: 'center',
            zIndex: 2,
          }}
        >
          {playbackState === 'connecting' ? (
            <>
              <RefreshCw size={36} color="#38bdf8" style={{ animation: 'spin 1.5s linear infinite', marginBottom: '12px' }} />
              <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#e2e8f0', letterSpacing: '0.06em' }}>
                CONNECTING TO LIVE STREAM...
              </div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', fontFamily: 'monospace', marginTop: '6px' }}>
                {streamUrl || activeHlsUrl}
              </div>
            </>
          ) : (
            <>
              <AlertTriangle size={40} color="#ef4444" style={{ marginBottom: '12px' }} />
              <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#f87171', letterSpacing: '0.05em' }}>
                {!isOnline
                  ? 'LIVE VIDEO CONNECTION LOST'
                  : errorMessage.toLowerCase().includes('network')
                  ? 'HLS GATEWAY / NETWORK ERROR'
                  : errorMessage.toLowerCase().includes('decode') || errorMessage.toLowerCase().includes('media')
                  ? 'MEDIA DECODE ERROR'
                  : 'LIVE VIDEO CONNECTION LOST'}
              </div>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8', fontFamily: 'monospace', marginTop: '6px' }}>
                {errorMessage || 'Live video stream unavailable or MediaMTX relay offline'}
              </div>
              <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '8px', maxWidth: '380px', lineHeight: 1.4 }}>
                Source: {streamUrl || activeHlsUrl}
              </div>
              <button
                onClick={() => setRetryCount((prev) => prev + 1)}
                style={{
                  marginTop: '12px',
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  color: '#38bdf8',
                  padding: '4px 12px',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <RefreshCw size={12} /> RETRY STREAM
              </button>
            </>
          )}
        </div>
      )}

      {/* Tactical C2 HUD Overlay */}
      {showOverlay && playbackState === 'playing' && (
        <>
          {/* Top-Left Camera HUD */}
          <div
            style={{
              position: 'absolute',
              top: '8px',
              left: '8px',
              backgroundColor: 'rgba(15, 23, 42, 0.85)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              padding: '3px 8px',
              borderRadius: '3px',
              fontSize: '0.65rem',
              color: '#38bdf8',
              fontFamily: 'monospace',
              zIndex: 10,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#ef4444' }} />
            <span>LIVE</span>
            <span style={{ color: '#64748b' }}>|</span>
            <span style={{ color: '#e2e8f0', fontWeight: 700 }}>{cameraId}</span>
            <span style={{ color: '#64748b' }}>|</span>
            <span style={{ color: '#00ffc8' }}>YOLO26S + BYTETRACK</span>
          </div>

          {/* Top-Right Control Ribbon */}
          <div
            style={{
              position: 'absolute',
              top: '8px',
              right: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              zIndex: 10,
            }}
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                setAiOverlayEnabled((prev) => !prev);
              }}
              style={{
                backgroundColor: aiOverlayEnabled ? 'rgba(2, 132, 199, 0.85)' : 'rgba(30, 41, 59, 0.85)',
                color: aiOverlayEnabled ? '#ffffff' : '#94a3b8',
                border: '1px solid ' + (aiOverlayEnabled ? '#38bdf8' : '#475569'),
                borderRadius: '3px',
                padding: '2px 8px',
                fontSize: '0.62rem',
                fontWeight: 700,
                fontFamily: 'monospace',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {aiOverlayEnabled ? '● AI OVERLAY ON' : '○ AI OVERLAY OFF'}
            </button>

            <div
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.85)',
                color: '#ffffff',
                padding: '2px 6px',
                borderRadius: '3px',
                fontSize: '0.6rem',
                fontWeight: 800,
                fontFamily: 'monospace',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#ffffff' }} />
              REC
            </div>
          </div>

          {/* Bottom-Left Sector Metadata */}
          <div
            style={{
              position: 'absolute',
              bottom: '8px',
              left: '8px',
              backgroundColor: 'rgba(15, 23, 42, 0.85)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              padding: '3px 8px',
              borderRadius: '3px',
              fontSize: '0.62rem',
              color: '#94a3b8',
              fontFamily: 'monospace',
              zIndex: 10,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>LOC: {sector.toUpperCase()}</span>
            {cameraName && (
              <>
                <span style={{ color: '#64748b' }}>|</span>
                <span style={{ color: '#38bdf8' }}>{cameraName}</span>
              </>
            )}
          </div>

          {/* Bottom-Right Live AI Inference Status & Metrics */}
          <div
            style={{
              position: 'absolute',
              bottom: '8px',
              right: '8px',
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              borderRadius: '4px',
              padding: '3px 10px',
              fontSize: '0.62rem',
              fontFamily: 'monospace',
              color: '#94a3b8',
              zIndex: 10,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span style={{ color: '#4ade80', fontWeight: 700 }}>
              ● YOLO26S + BYTETRACK
            </span>
            <span style={{ color: '#475569' }}>|</span>
            <span style={{ color: '#f8fafc' }}>
              {telemetry ? `${telemetry.fps} FPS` : '30.0 FPS'}
            </span>
            <span style={{ color: '#475569' }}>|</span>
            <span style={{ color: '#cbd5e1' }}>
              TRACKS: <strong style={{ color: '#38bdf8' }}>{telemetry?.active_tracks ?? 0}</strong>
            </span>
            {telemetry?.target_classes && telemetry.target_classes.length > 0 && (
              <>
                <span style={{ color: '#475569' }}>|</span>
                <span style={{ color: '#f59e0b', fontWeight: 700 }}>
                  {telemetry.target_classes.map((c) => c.toUpperCase()).join(', ')}
                </span>
              </>
            )}
          </div>

          {/* Real-time YOLO Bounding Boxes, Trajectory Trails & Virtual Counting Line Overlays */}
          {telemetry && aiOverlayEnabled && (
            <svg
              viewBox="0 0 720 480"
              preserveAspectRatio="none"
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
                zIndex: 3,
              }}
            >
              {/* Virtual Roadway Counting Line */}
              {telemetry.traffic?.counting_line && (
                <g>
                  {/* Outer Glow */}
                  <line
                    x1={telemetry.traffic.counting_line[0][0]}
                    y1={telemetry.traffic.counting_line[0][1]}
                    x2={telemetry.traffic.counting_line[1][0]}
                    y2={telemetry.traffic.counting_line[1][1]}
                    stroke="rgba(56, 189, 248, 0.35)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  {/* Core Dashed Line */}
                  <line
                    x1={telemetry.traffic.counting_line[0][0]}
                    y1={telemetry.traffic.counting_line[0][1]}
                    x2={telemetry.traffic.counting_line[1][0]}
                    y2={telemetry.traffic.counting_line[1][1]}
                    stroke="#38bdf8"
                    strokeWidth="2.5"
                    strokeDasharray="10 5"
                    strokeLinecap="round"
                  />
                  {/* Center Badge */}
                  <rect
                    x={(telemetry.traffic.counting_line[0][0] + telemetry.traffic.counting_line[1][0]) / 2 - 75}
                    y={telemetry.traffic.counting_line[0][1] - 18}
                    width="150"
                    height="17"
                    fill="rgba(15, 23, 42, 0.9)"
                    stroke="#38bdf8"
                    strokeWidth="1.2"
                    rx="3"
                  />
                  <text
                    x={(telemetry.traffic.counting_line[0][0] + telemetry.traffic.counting_line[1][0]) / 2}
                    y={telemetry.traffic.counting_line[0][1] - 5}
                    fill="#38bdf8"
                    fontSize="9.5"
                    fontFamily="monospace"
                    fontWeight="bold"
                    textAnchor="middle"
                  >
                    ⚡ VIRTUAL COUNTING LINE
                  </text>
                </g>
              )}

              {/* Detections, Trajectories & Labels */}
              {telemetry.detections?.map((det, idx) => {
                const [x1, y1, x2, y2] = det.bbox;
                const w = Math.max(0, x2 - x1);
                const h = Math.max(0, y2 - y1);
                const color = CLASS_COLOR_MAP[det.class_name.toLowerCase()] || '#38bdf8';
                const trackStr = det.track_id !== undefined && det.track_id !== null ? `#${det.track_id} ` : '';
                const label = `${trackStr}${det.class_name.toUpperCase()} ${Math.round(det.confidence * 100)}%`;
                const badgeW = label.length * 7.2 + 8;
                const centerX = (x1 + x2) / 2;
                const centerY = (y1 + y2) / 2;

                return (
                  <g key={`det-${idx}-${det.track_id || idx}`}>
                    {/* Motion Trajectory Trail */}
                    {det.trajectory && det.trajectory.length > 1 && (
                      <polyline
                        points={det.trajectory.map(([tx, ty]) => `${tx},${ty}`).join(' ')}
                        fill="none"
                        stroke={color}
                        strokeWidth="2.5"
                        strokeOpacity="0.75"
                        strokeLinecap="round"
                        strokeDasharray="4 2"
                      />
                    )}

                    {/* Bounding Box Rect */}
                    <rect
                      x={x1}
                      y={y1}
                      width={w}
                      height={h}
                      fill="rgba(56, 189, 248, 0.08)"
                      stroke={color}
                      strokeWidth="2.5"
                      strokeDasharray={det.confidence < 0.5 ? '4 2' : undefined}
                    />

                    {/* Center Tracking Dot */}
                    <circle
                      cx={centerX}
                      cy={centerY}
                      r="3.5"
                      fill="#facc15"
                      stroke="#000000"
                      strokeWidth="1"
                    />

                    {/* Corner Reticles */}
                    <path
                      d={`M ${x1} ${y1 + 8} L ${x1} ${y1} L ${x1 + 8} ${y1}`}
                      fill="none"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                    <path
                      d={`M ${x2 - 8} ${y1} L ${x2} ${y1} L ${x2} ${y1 + 8}`}
                      fill="none"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />

                    {/* Label Badge */}
                    <rect
                      x={x1}
                      y={Math.max(0, y1 - 18)}
                      width={badgeW}
                      height="18"
                      fill={color}
                      rx="2"
                    />
                    <text
                      x={x1 + 4}
                      y={Math.max(13, y1 - 4)}
                      fill="#000000"
                      fontSize="10"
                      fontWeight="800"
                      fontFamily="monospace"
                    >
                      {label}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </>
      )}
    </div>
  );
};
