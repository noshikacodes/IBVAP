import React, { useState } from 'react';
import { Alert } from '../types';
import { AlertCard } from './AlertCard';
import { Radio, CheckCircle } from 'lucide-react';

interface LiveAlertFeedProps {
  alerts: Alert[];
  onAcknowledge: (alertId: string) => void;
  onResolve: (alertId: string) => void;
  onInspect: (alert: Alert) => void;
  isActionLoading?: boolean;
}

export const LiveAlertFeed: React.FC<LiveAlertFeedProps> = ({
  alerts,
  onAcknowledge,
  onResolve,
  onInspect,
  isActionLoading = false,
}) => {
  const [filterUnacknowledged, setFilterUnacknowledged] = useState<boolean>(false);

  const displayedAlerts = filterUnacknowledged
    ? alerts.filter((a) => a.status === 'new')
    : alerts;

  return (
    <div
      style={{
        backgroundColor: '#0b1120',
        border: '1px solid #1e293b',
        borderRadius: '8px',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        maxHeight: '650px',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '0.85rem 1rem',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#0f172a',
          borderRadius: '8px 8px 0 0',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Radio size={16} color="#38bdf8" />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#f8fafc', letterSpacing: '0.04em' }}>
            LIVE SECURITY INCIDENT FEED
          </span>
          <span
            style={{
              backgroundColor: '#1e293b',
              color: '#94a3b8',
              fontSize: '0.7rem',
              fontWeight: 700,
              padding: '1px 6px',
              borderRadius: '10px',
            }}
          >
            {displayedAlerts.length}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={() => setFilterUnacknowledged(!filterUnacknowledged)}
            style={{
              backgroundColor: filterUnacknowledged ? '#2563eb' : '#1e293b',
              border: '1px solid #334155',
              color: filterUnacknowledged ? '#ffffff' : '#94a3b8',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '0.7rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {filterUnacknowledged ? 'Showing Pending Only' : 'Filter Pending'}
          </button>
        </div>
      </div>

      {/* Feed Content List */}
      <div style={{ padding: '0.75rem', overflowY: 'auto', flex: 1 }}>
        {displayedAlerts.length === 0 ? (
          <div
            style={{
              height: '180px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#64748b',
              gap: '8px',
              fontSize: '0.8rem',
            }}
          >
            <CheckCircle size={28} color="#10b981" />
            <div>No active perimeter violations detected</div>
            <div style={{ fontSize: '0.7rem', color: '#475569' }}>
              Streaming alerts will appear automatically via WebSocket
            </div>
          </div>
        ) : (
          displayedAlerts.map((alert) => (
            <AlertCard
              key={alert.alert_id}
              alert={alert}
              onAcknowledge={onAcknowledge}
              onResolve={onResolve}
              onInspect={onInspect}
              isActionLoading={isActionLoading}
            />
          ))
        )}
      </div>
    </div>
  );
};
