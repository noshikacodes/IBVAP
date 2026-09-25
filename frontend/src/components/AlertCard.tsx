import React from 'react';
import { Alert } from '../types';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';
import { Check, CheckCheck, Eye, MapPin, Radio, Clock } from 'lucide-react';

interface AlertCardProps {
  alert: Alert;
  onAcknowledge: (alertId: string) => void;
  onResolve: (alertId: string) => void;
  onInspect: (alert: Alert) => void;
  isActionLoading?: boolean;
}

export const AlertCard: React.FC<AlertCardProps> = ({
  alert,
  onAcknowledge,
  onResolve,
  onInspect,
  isActionLoading = false,
}) => {
  const formattedTime = new Date(alert.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  const zoneOrWire =
    alert.zone_id || alert.tripwire_id || alert.metadata?.zone_name || alert.metadata?.tripwire_name || 'Restricted Sector';

  return (
    <div
      style={{
        backgroundColor: '#0f172a',
        border: alert.severity === 'critical' ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid #1e293b',
        borderRadius: '6px',
        padding: '0.85rem 1rem',
        marginBottom: '0.65rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        boxShadow: alert.severity === 'critical' && alert.status === 'new' ? '0 0 10px rgba(239, 68, 68, 0.15)' : 'none',
      }}
    >
      {/* Top Header Row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <SeverityBadge severity={alert.severity} size="sm" />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#f1f5f9', letterSpacing: '0.02em' }}>
            {alert.event_type.toUpperCase()}
          </span>
          <StatusBadge status={alert.status} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#64748b' }}>
          <Clock size={12} />
          <span>{formattedTime}</span>
        </div>
      </div>

      {/* Target & Camera Metadata Row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', fontSize: '0.75rem', color: '#94a3b8' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#38bdf8' }}>
          <Radio size={12} /> {alert.camera_id}
        </span>
        <span style={{ color: '#cbd5e1', fontWeight: 600 }}>
          TRACK #{alert.track_id} ({alert.object_class.toUpperCase()})
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#94a3b8' }}>
          <MapPin size={12} /> {zoneOrWire}
        </span>
        {alert.metadata?.plate_number && (
          <span
            style={{
              backgroundColor: '#1e293b',
              color: '#facc15',
              border: '1px solid rgba(234, 179, 8, 0.4)',
              borderRadius: '4px',
              padding: '1px 6px',
              fontWeight: 700,
              fontFamily: 'monospace',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
            }}
          >
            🏷️ {alert.metadata.plate_number}
          </span>
        )}
        {alert.metadata?.identity_id && (
          <span
            style={{
              backgroundColor: alert.metadata.is_unknown ? '#1e293b' : '#064e3b',
              color: alert.metadata.is_unknown ? '#f87171' : '#34d399',
              border: alert.metadata.is_unknown ? '1px solid rgba(248, 113, 113, 0.4)' : '1px solid rgba(52, 211, 153, 0.4)',
              borderRadius: '4px',
              padding: '1px 6px',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
            }}
          >
            👤 {alert.metadata.display_name || alert.metadata.identity_id}
            {alert.metadata.similarity && !alert.metadata.is_unknown ? ` (${(alert.metadata.similarity * 100).toFixed(0)}%)` : ''}
          </span>
        )}
      </div>

      {/* Message */}
      <div style={{ fontSize: '0.8rem', color: '#e2e8f0', lineHeight: 1.35 }}>
        {alert.message}
      </div>

      {/* Actions Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '8px',
          paddingTop: '6px',
          borderTop: '1px solid #1e293b',
        }}
      >
        <button
          onClick={() => onInspect(alert)}
          style={{
            backgroundColor: 'transparent',
            border: '1px solid #334155',
            color: '#94a3b8',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '0.72rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <Eye size={12} /> Details
        </button>

        {alert.status === 'new' && (
          <button
            onClick={() => onAcknowledge(alert.alert_id)}
            disabled={isActionLoading}
            style={{
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              border: '1px solid #3b82f6',
              color: '#60a5fa',
              padding: '4px 10px',
              borderRadius: '4px',
              fontSize: '0.72rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Check size={12} /> Acknowledge
          </button>
        )}

        {alert.status === 'acknowledged' && (
          <button
            onClick={() => onResolve(alert.alert_id)}
            disabled={isActionLoading}
            style={{
              backgroundColor: 'rgba(34, 197, 94, 0.15)',
              border: '1px solid #22c55e',
              color: '#4ade80',
              padding: '4px 10px',
              borderRadius: '4px',
              fontSize: '0.72rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <CheckCheck size={12} /> Resolve
          </button>
        )}
      </div>
    </div>
  );
};
