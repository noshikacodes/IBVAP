import React, { useState, useEffect } from 'react';
import { CameraStreamInfo, Alert, PTZState } from '../types';
import { SeverityBadge } from '../components/SeverityBadge';
import { CCTVPlayer } from '../components/CCTVPlayer';
import { TrafficAnalyticsPanel } from '../components/TrafficAnalyticsPanel';
import {
  Radio,
  ShieldAlert,
  CheckCircle2,
  Info,
  AlertCircle,
  RefreshCw,
  Crosshair,
  ZoomIn,
  ZoomOut,
  Square,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Compass
} from 'lucide-react';

interface CamerasPageProps {
  cameras: CameraStreamInfo[];
  alerts: Alert[];
  onInspectAlert: (alert: Alert) => void;
}

export const CamerasPage: React.FC<CamerasPageProps> = ({
  cameras,
  alerts,
  onInspectAlert,
}) => {
  const [selectedCameraId, setSelectedCameraId] = useState<string>(() => {
    const liveCam = cameras.find((c) => c.id.includes('95366') || c.id.includes('SEJONG'));
    return liveCam ? liveCam.id : (cameras[0]?.id || 'CAM_SEJONG_95366');
  });

  const [ptzState, setPtzState] = useState<PTZState>({
    camera_id: selectedCameraId,
    connection_state: 'CONNECTED',
    pan: 0.0,
    tilt: 0.0,
    zoom: 1.0,
    driver_type: 'simulator',
  });
  const [ptzLoading, setPtzLoading] = useState<boolean>(false);

  // Fetch live PTZ status when camera changes
  useEffect(() => {
    const fetchPtzStatus = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/cameras/${selectedCameraId}/ptz`);
        if (res.ok) {
          const data = await res.json();
          setPtzState(data);
        }
      } catch (err) {
        // Fallback local simulated state
        setPtzState((prev) => ({ ...prev, camera_id: selectedCameraId }));
      }
    };
    fetchPtzStatus();
  }, [selectedCameraId]);

  const handlePtzMove = async (deltaPan: number, deltaTilt: number, deltaZoom: number) => {
    setPtzLoading(true);
    const newPan = Math.max(-180, Math.min(180, ptzState.pan + deltaPan));
    const newTilt = Math.max(-90, Math.min(90, ptzState.tilt + deltaTilt));
    const newZoom = Math.max(1.0, Math.min(30.0, ptzState.zoom + deltaZoom));

    try {
      const res = await fetch(`http://localhost:8000/api/v1/cameras/${selectedCameraId}/ptz/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pan: newPan, tilt: newTilt, zoom: newZoom }),
      });
      if (res.ok) {
        const data = await res.json();
        setPtzState((prev) => ({
          ...prev,
          pan: data.position.pan,
          tilt: data.position.tilt,
          zoom: data.position.zoom,
          connection_state: 'CONNECTED',
          last_command_id: data.command_id,
          last_command_status: data.status,
        }));
      }
    } catch (err) {
      // Offline fallback
      setPtzState((prev) => ({
        ...prev,
        pan: newPan,
        tilt: newTilt,
        zoom: newZoom,
      }));
    } finally {
      setPtzLoading(false);
    }
  };

  const handlePtzStop = async () => {
    try {
      await fetch(`http://localhost:8000/api/v1/cameras/${selectedCameraId}/ptz/stop`, {
        method: 'POST',
      });
      setPtzState((prev) => ({ ...prev, connection_state: 'STOPPED' }));
    } catch (err) {
      setPtzState((prev) => ({ ...prev, connection_state: 'STOPPED' }));
    }
  };

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId) || cameras[0];
  const cameraAlerts = alerts.filter(
    (a) => a.camera_id === selectedCameraId && a.status !== 'resolved'
  );


  const renderStatusBadge = (cam: CameraStreamInfo) => {
    if (!cam.is_simulated && cam.status === 'online') {
      return (
        <span
          style={{
            backgroundColor: 'rgba(16, 185, 129, 0.2)',
            color: '#34d399',
            border: '1px solid rgba(16, 185, 129, 0.5)',
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '0.68rem',
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }} />
          REAL CAMERA • LIVE
        </span>
      );
    }

    switch (cam.status) {
      case 'online':
        return (
          <span
            style={{
              backgroundColor: 'rgba(34, 197, 94, 0.15)',
              color: '#4ade80',
              border: '1px solid rgba(34, 197, 94, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.68rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
            LIVE RTSP
          </span>
        );
      case 'connecting':
        return (
          <span
            style={{
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              color: '#38bdf8',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.68rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <RefreshCw size={10} style={{ animation: 'spin 1.5s linear infinite' }} />
            CONNECTING...
          </span>
        );
      case 'reconnecting':
        return (
          <span
            style={{
              backgroundColor: 'rgba(249, 115, 22, 0.15)',
              color: '#fb923c',
              border: '1px solid rgba(249, 115, 22, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.68rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <RefreshCw size={10} style={{ animation: 'spin 1s linear infinite' }} />
            RECONNECTING
          </span>
        );
      case 'degraded':
        return (
          <span
            style={{
              backgroundColor: 'rgba(234, 179, 8, 0.15)',
              color: '#facc15',
              border: '1px solid rgba(234, 179, 8, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.68rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <AlertCircle size={10} />
            DEGRADED
          </span>
        );
      case 'offline':
        return (
          <span
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.68rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <AlertCircle size={10} />
            OFFLINE
          </span>
        );
      case 'simulated':
      default:
        return (
          <span
            style={{
              backgroundColor: 'rgba(168, 85, 247, 0.15)',
              color: '#c084fc',
              border: '1px solid rgba(168, 85, 247, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.68rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#a855f7' }} />
            SIMULATED / DEMO
          </span>
        );
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Page Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #1e293b',
          paddingBottom: '1rem',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 4px 0', color: '#f8fafc' }}>
            Surveillance Stream Matrix & CCTV Ingestion
          </h2>
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
            Software-defined RTSP/CCTV stream management, ingestion diagnostics, and live sector monitoring
          </p>
        </div>

        {/* Demo Notice Banner */}
        <div
          style={{
            backgroundColor: 'rgba(234, 179, 8, 0.12)',
            border: '1px solid rgba(234, 179, 8, 0.3)',
            borderRadius: '6px',
            padding: '6px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.75rem',
            color: '#facc15',
          }}
        >
          <Info size={15} />
          <span>
            Live RTSP connects via MediaMTX (:8554). Simulated feeds operate via local benchmark video.
          </span>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(520px, 1.35fr) minmax(380px, 1.15fr)', gap: '1.25rem', alignItems: 'start' }}>
        {/* Left: Selected Camera Live Viewport & Calibration Panel */}
        {selectedCamera && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Viewport Header */}
              <div
                style={{
                  padding: '0.85rem 1rem',
                  borderBottom: '1px solid #1e293b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  backgroundColor: '#090d16',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Radio size={16} color="#38bdf8" />
                  <span style={{ fontWeight: 800, fontSize: '0.9rem', color: '#f8fafc' }}>
                    {selectedCamera.name} ({selectedCamera.id})
                  </span>
                  {renderStatusBadge(selectedCamera)}
                </div>

                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                  {selectedCamera.resolution} @ {selectedCamera.fps} FPS
                </div>
              </div>

              {/* Tactical Pipeline Flow Status Banner */}
              <div
                style={{
                  backgroundColor: '#0b1329',
                  borderBottom: '1px solid #1e293b',
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  overflowX: 'auto',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.68rem', fontFamily: 'monospace' }}>
                  <span style={{ backgroundColor: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.4)', padding: '2px 6px', borderRadius: '3px', fontWeight: 700 }}>
                    LIVE CAMERA
                  </span>
                  <span style={{ color: '#64748b' }}>➔</span>
                  <span style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.4)', padding: '2px 6px', borderRadius: '3px', fontWeight: 700 }}>
                    {selectedCamera.id === 'CAM_SEJONG_95366' ? 'GITS-95366' : selectedCamera.id}
                  </span>
                  <span style={{ color: '#64748b' }}>➔</span>
                  <span style={{ backgroundColor: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.4)', padding: '2px 6px', borderRadius: '3px', fontWeight: 700 }}>
                    {selectedCamera.id.includes('95366') || selectedCamera.id.includes('1809') || selectedCamera.id.includes('GITS') ? 'HLS STREAM' : 'RTSP STREAM'}
                  </span>
                  <span style={{ color: '#64748b' }}>➔</span>
                  <span style={{ backgroundColor: 'rgba(234, 179, 8, 0.2)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.4)', padding: '2px 6px', borderRadius: '3px', fontWeight: 700 }}>
                    FRAME INGESTION
                  </span>
                  <span style={{ color: '#64748b' }}>➔</span>
                  <span style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)', padding: '2px 6px', borderRadius: '3px', fontWeight: 700 }}>
                    YOLO DETECTION
                  </span>
                  <span style={{ color: '#64748b' }}>➔</span>
                  <span style={{ backgroundColor: 'rgba(14, 165, 233, 0.2)', color: '#38bdf8', border: '1px solid rgba(14, 165, 233, 0.4)', padding: '2px 6px', borderRadius: '3px', fontWeight: 700 }}>
                    BYTE TRACK
                  </span>
                  <span style={{ color: '#64748b' }}>➔</span>
                  <span style={{ backgroundColor: 'rgba(16, 185, 129, 0.2)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.4)', padding: '2px 6px', borderRadius: '3px', fontWeight: 700 }}>
                    ANALYTICS
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.65rem', fontFamily: 'monospace', color: '#94a3b8' }}>
                  <span style={{ color: '#22c55e', fontWeight: 700 }}>● CONNECTED</span>
                  <span>|</span>
                  <span>{selectedCamera.resolution}</span>
                  <span>|</span>
                  <span>{selectedCamera.fps} FPS</span>
                </div>
              </div>

              {/* Video Player Display Simulation */}
              <div
                style={{
                  height: '480px',
                  backgroundColor: '#020617',
                  position: 'relative',
                  overflow: 'hidden',
                  borderRadius: '0',
                }}
              >
                <CCTVPlayer
                  streamUrl={selectedCamera.video_source}
                  sourceType={selectedCamera.source_type}
                  cameraId={selectedCamera.id}
                  cameraName={selectedCamera.name}
                  sector={selectedCamera.sector}
                  isOnline={selectedCamera.status === 'online' || selectedCamera.is_simulated}
                  showOverlay={true}
                  aspectRatio="auto"
                />

                {/* Bottom Threat Indicator */}
                {cameraAlerts.length > 0 && (
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '12px',
                      left: '12px',
                      backgroundColor: 'rgba(239, 68, 68, 0.9)',
                      color: '#ffffff',
                      padding: '4px 10px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      zIndex: 3,
                    }}
                  >
                    <ShieldAlert size={14} />
                    <span>{cameraAlerts.length} UNRESOLVED INCIDENTS DETECTED</span>
                  </div>
                )}
              </div>

              {/* Stream Diagnostics Footer */}
              <div
                style={{
                  padding: '0.85rem 1rem',
                  borderTop: '1px solid #1e293b',
                  backgroundColor: '#090d16',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '12px',
                  justifyContent: 'space-between',
                  fontSize: '0.75rem',
                  color: '#94a3b8',
                }}
              >
                <div>
                  <strong>Location:</strong> {selectedCamera.sector}
                </div>
                <div>
                  <strong>RTSP Endpoint:</strong> <code style={{ color: '#38bdf8' }}>{selectedCamera.video_source}</code>
                </div>
              </div>
            </div>

            {/* Camera Calibration & Field Configuration Panel */}
            <div
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 800, fontSize: '0.92rem', color: '#f8fafc' }}>
                    Camera Field Calibration & Stream Diagnostics ({selectedCamera.id})
                  </span>
                </div>
                {renderStatusBadge(selectedCamera)}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>Resolution & FPS</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc', marginTop: '2px' }}>
                    {selectedCamera.resolution} @ {selectedCamera.fps} FPS
                  </div>
                </div>

                <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>Transport Protocol</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#38bdf8', marginTop: '2px' }}>
                    {selectedCamera.transport?.toUpperCase() || 'TCP (RTSP Interleaved)'}
                  </div>
                </div>

                <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>IR Night Mode</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: selectedCamera.night_mode ? '#4ade80' : '#94a3b8', marginTop: '2px' }}>
                    {selectedCamera.night_mode ? 'ACTIVE (Low-Light IR)' : 'STANDARD'}
                  </div>
                </div>

                <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>Min Object Size</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc', marginTop: '2px' }}>
                    {selectedCamera.min_object_size || 16} px
                  </div>
                </div>
              </div>

              {/* Edge Analytics Capabilities Grid */}
              <div style={{ borderTop: '1px solid #1e293b', paddingTop: '0.75rem' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', marginBottom: '0.5rem' }}>
                  EDGE ANALYTICS PIPELINES
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ backgroundColor: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '4px 10px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                    ✓ YOLO Detection & Tracking
                  </span>
                  <span style={{ backgroundColor: selectedCamera.id === 'CAM_GATE' || selectedCamera.id === 'CAM_01' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(100, 116, 139, 0.15)', color: selectedCamera.id === 'CAM_GATE' || selectedCamera.id === 'CAM_01' ? '#4ade80' : '#64748b', border: '1px solid rgba(100, 116, 139, 0.3)', padding: '4px 10px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                    ANPR License Plate OCR
                  </span>
                  <span style={{ backgroundColor: selectedCamera.id === 'CAM_PATROL' || selectedCamera.id === 'CAM_02' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(100, 116, 139, 0.15)', color: selectedCamera.id === 'CAM_PATROL' || selectedCamera.id === 'CAM_02' ? '#4ade80' : '#64748b', border: '1px solid rgba(100, 116, 139, 0.3)', padding: '4px 10px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                    FRS Biometric Recognition
                  </span>
                  <span style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.3)', padding: '4px 10px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                    ✓ Spatial Geofences & Tripwires
                  </span>
                </div>
              </div>
            </div>

            {/* PTZ Slew-to-Cue & Tactical Joystick Control Panel */}
            <div
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Compass size={18} color="#38bdf8" />
                  <span style={{ fontWeight: 800, fontSize: '0.92rem', color: '#f8fafc' }}>
                    PTZ Slew-to-Cue & Tactical Override ({selectedCamera.id})
                  </span>
                </div>
                <span
                  style={{
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    color: '#38bdf8',
                    border: '1px solid rgba(56, 189, 248, 0.4)',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '0.68rem',
                    fontWeight: 700,
                  }}
                >
                  DRIVER: {ptzState.driver_type.toUpperCase()} ({ptzState.connection_state})
                </span>
              </div>

              {/* Live Target Cue Callout (if active target) */}
              {ptzState.current_target && (
                <div
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    marginBottom: '1rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.75rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f87171', fontWeight: 700 }}>
                    <Crosshair size={16} />
                    <span>TARGET ACQUIRED // AUTO-SLEW ENGAGED</span>
                  </div>
                  <div style={{ color: '#fca5a5', fontFamily: 'monospace' }}>
                    TRACK #{ptzState.current_target.track_id || 'UNKNOWN'} • {ptzState.current_target.event_type?.toUpperCase()}
                  </div>
                </div>
              )}

              {/* Position Telemetry Readout */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.68rem', color: '#64748b' }}>PAN ANGLE</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'monospace' }}>
                    {ptzState.pan.toFixed(1)}°
                  </div>
                </div>
                <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.68rem', color: '#64748b' }}>TILT ELEVATION</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'monospace' }}>
                    {ptzState.tilt.toFixed(1)}°
                  </div>
                </div>
                <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.68rem', color: '#64748b' }}>OPTICAL ZOOM</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#4ade80', fontFamily: 'monospace' }}>
                    {ptzState.zoom.toFixed(1)}x
                  </div>
                </div>
              </div>

              {/* Tactical Direction & Zoom Controls */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', alignItems: 'center', justifyContent: 'center', backgroundColor: '#090d16', padding: '1rem', borderRadius: '8px', border: '1px solid #1e293b' }}>
                {/* Direction Pad */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 38px)', gridTemplateRows: 'repeat(3, 38px)', gap: '6px' }}>
                  <div />
                  <button
                    onClick={() => handlePtzMove(0, 10, 0)}
                    disabled={ptzLoading}
                    title="Tilt Up"
                    style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '4px', color: '#f8fafc', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >
                    <ArrowUp size={16} />
                  </button>
                  <div />

                  <button
                    onClick={() => handlePtzMove(-15, 0, 0)}
                    disabled={ptzLoading}
                    title="Pan Left"
                    style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '4px', color: '#f8fafc', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >
                    <ArrowLeft size={16} />
                  </button>

                  <button
                    onClick={() => handlePtzMove(-ptzState.pan, -ptzState.tilt, 0)}
                    disabled={ptzLoading}
                    title="Center / Home"
                    style={{ backgroundColor: '#0f172a', border: '1px solid #38bdf8', borderRadius: '4px', color: '#38bdf8', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.68rem', fontWeight: 800 }}
                  >
                    HOME
                  </button>

                  <button
                    onClick={() => handlePtzMove(15, 0, 0)}
                    disabled={ptzLoading}
                    title="Pan Right"
                    style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '4px', color: '#f8fafc', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >
                    <ArrowRight size={16} />
                  </button>

                  <div />
                  <button
                    onClick={() => handlePtzMove(0, -10, 0)}
                    disabled={ptzLoading}
                    title="Tilt Down"
                    style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '4px', color: '#f8fafc', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >
                    <ArrowDown size={16} />
                  </button>
                  <div />
                </div>

                {/* Zoom & Safety Controls */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => handlePtzMove(0, 0, 1.0)}
                      disabled={ptzLoading}
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', padding: '6px 12px', color: '#f8fafc', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}
                    >
                      <ZoomIn size={14} color="#4ade80" /> Zoom +
                    </button>
                    <button
                      onClick={() => handlePtzMove(0, 0, -1.0)}
                      disabled={ptzLoading}
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', padding: '6px 12px', color: '#f8fafc', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}
                    >
                      <ZoomOut size={14} color="#f87171" /> Zoom -
                    </button>
                  </div>

                  <button
                    onClick={handlePtzStop}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: '6px', padding: '6px 12px', color: '#f87171', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                  >
                    <Square size={12} /> EMERGENCY STOP
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Right: Real-time Traffic Intelligence Data Window & Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Traffic Intelligence & Historical Counting Data Window */}
          {(selectedCameraId.includes('95366') || selectedCameraId.includes('SEJONG') || selectedCameraId.includes('1809') || selectedCameraId.includes('GITS') || selectedCameraId === 'CAM_01') && (
            <TrafficAnalyticsPanel
              cameraId={selectedCameraId}
              cameraName={selectedCamera?.name}
            />
          )}

          {/* Camera List Selector */}
          <div
            style={{
              backgroundColor: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '1rem',
            }}
          >
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.75rem' }}>
              Configured Surveillance Cameras
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {cameras.map((cam) => {
                const isSelected = cam.id === selectedCameraId;
                const camUnresolved = alerts.filter(
                  (a) => a.camera_id === cam.id && a.status !== 'resolved'
                );

                return (
                  <button
                    key={cam.id}
                    onClick={() => setSelectedCameraId(cam.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.65rem 0.85rem',
                      borderRadius: '6px',
                      border: isSelected ? '1px solid #38bdf8' : '1px solid #1e293b',
                      backgroundColor: isSelected ? '#1e293b' : '#090d16',
                      color: '#f8fafc',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.82rem' }}>{cam.name}</div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                        {cam.id} • {cam.sector}
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {camUnresolved.length > 0 && (
                        <span
                          style={{
                            backgroundColor: '#ef4444',
                            color: '#ffffff',
                            padding: '1px 6px',
                            borderRadius: '10px',
                            fontSize: '0.68rem',
                            fontWeight: 700,
                          }}
                        >
                          {camUnresolved.length}
                        </span>
                      )}
                      {renderStatusBadge(cam)}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Active Threats on Selected Camera */}
          <div
            style={{
              backgroundColor: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '1rem',
            }}
          >
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>Recent Incidents ({selectedCameraId})</span>
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>{cameraAlerts.length} Active</span>
            </div>

            {cameraAlerts.length === 0 ? (
              <div style={{ fontSize: '0.78rem', color: '#64748b', textAlign: 'center', padding: '1.5rem 0' }}>
                <CheckCircle2 size={24} color="#10b981" style={{ margin: '0 auto 6px auto' }} />
                <div>No active incidents on this sector feed</div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '240px', overflowY: 'auto' }}>
                {cameraAlerts.slice(0, 5).map((alt) => (
                  <div
                    key={alt.alert_id}
                    onClick={() => onInspectAlert(alt)}
                    style={{
                      backgroundColor: '#090d16',
                      border: '1px solid #1e293b',
                      borderRadius: '5px',
                      padding: '8px',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                      <SeverityBadge severity={alt.severity} size="sm" />
                      <span style={{ color: '#64748b', fontSize: '0.68rem', fontFamily: 'monospace' }}>
                        {new Date(alt.timestamp).toLocaleTimeString([], { hour12: false })}
                      </span>
                    </div>
                    <div style={{ color: '#e2e8f0', fontWeight: 600 }}>
                      TRACK #{alt.track_id} — {alt.event_type.toUpperCase()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

