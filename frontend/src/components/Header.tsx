import React, { useState, useEffect } from 'react';
import { Radio, RefreshCw, AlertCircle, ShieldAlert } from 'lucide-react';
import { WebSocketStatus, HealthResponse } from '../types';

interface HeaderProps {
  wsStatus: WebSocketStatus;
  health: HealthResponse | null;
  totalAlerts?: number;
  criticalAlerts: number;
  cameras?: import('../types').CameraStreamInfo[];
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  wsStatus,
  health,
  criticalAlerts,
  cameras = [],
  onRefresh,
  isRefreshing = false,
}) => {
  const [timeStr, setTimeStr] = useState<string>('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(now.toUTCString().replace('GMT', 'UTC'));
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  const liveCameras = cameras.filter((c) => c.status === 'online');
  const hasLiveRtsp = liveCameras.length > 0;
  const hasSimulated = cameras.some((c) => c.is_simulated || c.status === 'simulated');

  const streamStatusBadge = () => {
    if (hasLiveRtsp) {
      const camIds = liveCameras.map((c) => c.id).join(', ');
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            backgroundColor: 'rgba(34, 197, 94, 0.15)',
            color: '#4ade80',
            border: '1px solid rgba(34, 197, 94, 0.4)',
            padding: '3px 8px',
            borderRadius: '4px',
            fontSize: '0.72rem',
            fontWeight: 700,
          }}
          title="Active RTSP stream ingestion from MediaMTX relay"
        >
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
          LIVE RTSP ({camIds})
        </span>
      );
    }

    if (hasSimulated) {
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            backgroundColor: 'rgba(234, 179, 8, 0.15)',
            color: '#facc15',
            border: '1px solid rgba(234, 179, 8, 0.4)',
            padding: '3px 8px',
            borderRadius: '4px',
            fontSize: '0.72rem',
            fontWeight: 700,
          }}
          title="Operating in simulated / benchmark video mode"
        >
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#eab308' }} />
          SIMULATED / DEMO
        </span>
      );
    }

    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          color: '#f87171',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          padding: '3px 8px',
          borderRadius: '4px',
          fontSize: '0.72rem',
          fontWeight: 700,
        }}
      >
        🔴 STREAMS OFFLINE
      </span>
    );
  };

  const wsBadge = () => {
    switch (wsStatus) {
      case 'connected':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              backgroundColor: 'rgba(56, 189, 248, 0.12)',
              color: '#38bdf8',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '0.72rem',
              fontWeight: 700,
            }}
            title="Real-time WebSocket event connection active"
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#38bdf8' }} />
            C2 LINK ACTIVE
          </span>
        );
      case 'connecting':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              backgroundColor: 'rgba(234, 179, 8, 0.12)',
              color: '#facc15',
              border: '1px solid rgba(234, 179, 8, 0.3)',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '0.72rem',
              fontWeight: 700,
            }}
          >
            🟡 CONNECTING C2...
          </span>
        );
      case 'disconnected':
      case 'error':
      default:
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              backgroundColor: 'rgba(239, 68, 68, 0.12)',
              color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '0.72rem',
              fontWeight: 700,
            }}
          >
            🔴 C2 DISCONNECTED
          </span>
        );
    }
  };

  return (
    <header
      style={{
        height: '60px',
        backgroundColor: '#0f172a',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.5rem',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      {/* Left: System Status Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Radio size={16} color="#38bdf8" />
          <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f1f5f9', letterSpacing: '0.02em' }}>
            BORDER SECTOR ALPHA
          </span>
        </div>
        {streamStatusBadge()}
        {wsBadge()}
        {health ? (
          <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
            Gateway: v{health.version}
          </span>
        ) : (
          <span style={{ fontSize: '0.72rem', color: '#ef4444', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <AlertCircle size={12} /> Gateway Offline
          </span>
        )}
      </div>

      {/* Right: Live Ticker & Quick Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {criticalAlerts > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid #ef4444',
              color: '#f87171',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '0.72rem',
              fontWeight: 700,
            }}
          >
            <ShieldAlert size={14} />
            <span>{criticalAlerts} CRITICAL THREATS</span>
          </div>
        )}

        <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontFamily: 'monospace' }}>
          {timeStr}
        </div>

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh platform data"
          style={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            color: '#cbd5e1',
            padding: '6px 10px',
            borderRadius: '5px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.75rem',
            fontWeight: 600,
          }}
        >
          <RefreshCw size={13} style={{ animation: isRefreshing ? 'spin 1s linear infinite' : 'none' }} />
          <span>Sync</span>
        </button>
      </div>
    </header>
  );
};
