import React from 'react';
import { Alert, CameraStreamInfo } from '../types';
import { KPICards } from '../components/KPICards';
import { LiveAlertFeed } from '../components/LiveAlertFeed';
import { CCTVPlayer } from '../components/CCTVPlayer';
import { Video, Radio, MapPin, AlertTriangle } from 'lucide-react';

interface DashboardHomeProps {
  alerts: Alert[];
  cameras: CameraStreamInfo[];
  onAcknowledge: (alertId: string) => void;
  onResolve: (alertId: string) => void;
  onInspect: (alert: Alert) => void;
  onSelectCamera: (cameraId: string) => void;
  isActionLoading?: boolean;
}

export const DashboardHome: React.FC<DashboardHomeProps> = ({
  alerts,
  cameras,
  onAcknowledge,
  onResolve,
  onInspect,
  onSelectCamera,
  isActionLoading = false,
}) => {
  const newAlerts = alerts.filter((a) => a.status === 'new').length;
  const criticalAlerts = alerts.filter((a) => a.severity === 'critical' && a.status !== 'resolved').length;
  const uniqueViolators = new Set(alerts.map((a) => a.track_id)).size;
  const simulatedCount = cameras.filter((c) => c.is_simulated || c.status === 'simulated').length;
  const liveCount = cameras.filter((c) => c.status === 'online').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* KPI Metrics Summary Row */}
      <KPICards
        totalCameras={cameras.length}
        simulatedCameras={simulatedCount}
        liveCameras={liveCount}
        totalAlerts={alerts.length}
        newAlerts={newAlerts}
        criticalAlerts={criticalAlerts}
        uniqueViolatorsCount={uniqueViolators}
      />

      {/* Main Operational Split Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(400px, 1.2fr) minmax(360px, 1fr)',
          gap: '1.25rem',
          alignItems: 'start',
        }}
      >
        {/* Left Column: Surveillance Grid Quick-View */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div
            style={{
              backgroundColor: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '1rem',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '1rem',
                borderBottom: '1px solid #1e293b',
                paddingBottom: '0.65rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Video size={18} color="#38bdf8" />
                <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f8fafc' }}>
                  SURVEILLANCE SECTOR STREAMS
                </span>
              </div>
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                {cameras.length} Monitored Feeds
              </span>
            </div>

            {/* Camera Grid Tiles */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '0.85rem',
              }}
            >
              {cameras.map((cam) => {
                const camAlerts = alerts.filter(
                  (a) => a.camera_id === cam.id && a.status !== 'resolved'
                );

                return (
                  <div
                    key={cam.id}
                    onClick={() => onSelectCamera(cam.id)}
                    style={{
                      backgroundColor: '#090d16',
                      border: camAlerts.length > 0 ? '1px solid #ef444466' : '1px solid #1e293b',
                      borderRadius: '6px',
                      overflow: 'hidden',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                  >
                    {/* Video Canvas Simulation Viewport */}
                    <div
                      style={{
                        height: '130px',
                        backgroundColor: '#050811',
                        position: 'relative',
                        overflow: 'hidden',
                        borderBottom: '1px solid #1e293b',
                      }}
                    >
                      <CCTVPlayer
                        streamUrl={cam.video_source}
                        sourceType={cam.source_type}
                        cameraId={cam.id}
                        cameraName={cam.name}
                        sector={cam.sector}
                        isOnline={cam.status === 'online' || cam.is_simulated}
                        showOverlay={false}
                        aspectRatio="auto"
                      />

                      {/* Status Badges on Viewport */}
                      <div
                        style={{
                          position: 'absolute',
                          top: '6px',
                          left: '6px',
                          backgroundColor: 'rgba(15, 23, 42, 0.85)',
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          color: '#38bdf8',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <Radio size={10} /> {cam.id}
                      </div>

                      <div
                        style={{
                          position: 'absolute',
                          top: '6px',
                          right: '6px',
                          backgroundColor: (!cam.is_simulated && cam.status === 'online')
                            ? 'rgba(16, 185, 129, 0.2)'
                            : cam.is_simulated
                            ? 'rgba(168, 85, 247, 0.2)'
                            : cam.status === 'connecting'
                            ? 'rgba(234, 179, 8, 0.2)'
                            : 'rgba(239, 68, 68, 0.2)',
                          color: (!cam.is_simulated && cam.status === 'online')
                            ? '#34d399'
                            : cam.is_simulated
                            ? '#c084fc'
                            : cam.status === 'connecting'
                            ? '#facc15'
                            : '#f87171',
                          border: `1px solid ${
                            (!cam.is_simulated && cam.status === 'online')
                              ? '#10b98155'
                              : cam.is_simulated
                              ? '#a855f755'
                              : cam.status === 'connecting'
                              ? '#eab30855'
                              : '#ef444455'
                          }`,
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '0.62rem',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          letterSpacing: '0.03em',
                        }}
                      >
                        {(!cam.is_simulated && cam.status === 'online')
                          ? 'REAL CAMERA • LIVE'
                          : cam.is_simulated
                          ? 'SIMULATED / DEMO'
                          : cam.status.toUpperCase()}
                      </div>

                      {camAlerts.length > 0 && (
                        <div
                          style={{
                            position: 'absolute',
                            bottom: '6px',
                            right: '6px',
                            backgroundColor: 'rgba(239, 68, 68, 0.9)',
                            color: '#ffffff',
                            padding: '2px 6px',
                            borderRadius: '3px',
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <AlertTriangle size={10} /> {camAlerts.length} THREATS
                        </div>
                      )}
                    </div>

                    {/* Camera Info Footer */}
                    <div style={{ padding: '0.65rem 0.75rem', fontSize: '0.75rem' }}>
                      <div style={{ fontWeight: 700, color: '#f1f5f9', marginBottom: '2px' }}>
                        {cam.name}
                      </div>
                      <div style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <MapPin size={11} /> {cam.sector} • {cam.resolution}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Live Streaming Alert Feed */}
        <div>
          <LiveAlertFeed
            alerts={alerts}
            onAcknowledge={onAcknowledge}
            onResolve={onResolve}
            onInspect={onInspect}
            isActionLoading={isActionLoading}
          />
        </div>
      </div>
    </div>
  );
};
