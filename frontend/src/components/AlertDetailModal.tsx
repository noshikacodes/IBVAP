import React, { useState } from 'react';
import { Alert } from '../types';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';
import { X, Check, CheckCheck, MapPin, Radio, Shield } from 'lucide-react';

interface AlertDetailModalProps {
  alert: Alert | null;
  onClose: () => void;
  onAcknowledge: (alertId: string) => void;
  onResolve: (alertId: string, notes?: string) => void;
  isActionLoading?: boolean;
}

export const AlertDetailModal: React.FC<AlertDetailModalProps> = ({
  alert,
  onClose,
  onAcknowledge,
  onResolve,
  isActionLoading = false,
}) => {
  const [resolutionNotes, setResolutionNotes] = useState<string>('');

  if (!alert) return null;

  const handleResolveSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onResolve(alert.alert_id, resolutionNotes);
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#0f172a',
          border: '1px solid #334155',
          borderRadius: '8px',
          width: '100%',
          maxWidth: '640px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '1rem 1.25rem',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: '#1e293b55',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={18} color="#38bdf8" />
            <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#f8fafc' }}>
              Security Incident Inspection
            </span>
            <SeverityBadge severity={alert.severity} size="sm" />
            <StatusBadge status={alert.status} />
          </div>
          <button
            onClick={onClose}
            style={{
              backgroundColor: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              padding: '4px',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Key Identifiers */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>ALERT ID</div>
              <div style={{ fontSize: '0.8rem', color: '#38bdf8', fontFamily: 'monospace', fontWeight: 700 }}>{alert.alert_id}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>EVENT TRACE ID</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontFamily: 'monospace' }}>{alert.event_id || 'N/A'}</div>
            </div>
          </div>

          {/* Core Info Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.8rem' }}>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem', fontWeight: 600 }}>CAMERA STREAM</span>
              <span style={{ color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
                <Radio size={13} color="#38bdf8" /> {alert.camera_id}
              </span>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem', fontWeight: 600 }}>TARGET IDENTIFIER</span>
              <span style={{ color: '#f1f5f9', fontWeight: 700, marginTop: '2px', display: 'block' }}>
                TRACK #{alert.track_id} ({alert.object_class.toUpperCase()})
              </span>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem', fontWeight: 600 }}>ZONE / TRIPWIRE</span>
              <span style={{ color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
                <MapPin size={13} color="#f59e0b" /> {alert.zone_id || alert.tripwire_id || 'Restricted Perimeter'}
              </span>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem', fontWeight: 600 }}>SPATIAL POSITION (X, Y)</span>
              <span style={{ color: '#94a3b8', fontFamily: 'monospace', marginTop: '2px', display: 'block' }}>
                [{alert.position[0].toFixed(1)}, {alert.position[1].toFixed(1)}] px
              </span>
            </div>
          </div>

          {/* ANPR Vehicle Identification Section */}
          {alert.metadata?.plate_number && (
            <div
              style={{
                backgroundColor: '#1e293b44',
                border: '1px solid rgba(234, 179, 8, 0.35)',
                borderRadius: '6px',
                padding: '0.75rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div style={{ fontSize: '0.7rem', color: '#facc15', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                🏷️ AUTOMATIC NUMBER PLATE RECOGNITION (ANPR)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>VERIFIED PLATE: </span>
                  <span style={{ fontSize: '1rem', color: '#fef08a', fontFamily: 'monospace', fontWeight: 800, letterSpacing: '0.05em' }}>
                    {alert.metadata.plate_number}
                  </span>
                </div>
                {alert.metadata.plate_format && (
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                    Format: <span style={{ color: '#38bdf8', fontWeight: 600 }}>{alert.metadata.plate_format}</span>
                  </div>
                )}
                {alert.metadata.confidence !== undefined && (
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                    OCR Conf: <span style={{ color: '#4ade80', fontWeight: 600 }}>{(alert.metadata.confidence * 100).toFixed(1)}%</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Facial Recognition (FRS) Section */}
          {alert.metadata?.identity_id && (
            <div
              style={{
                backgroundColor: alert.metadata.is_unknown ? '#1e293b44' : '#064e3b22',
                border: alert.metadata.is_unknown ? '1px solid rgba(248, 113, 113, 0.35)' : '1px solid rgba(52, 211, 153, 0.35)',
                borderRadius: '6px',
                padding: '0.75rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div style={{ fontSize: '0.7rem', color: alert.metadata.is_unknown ? '#f87171' : '#34d399', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                👤 FACIAL RECOGNITION (FRS)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>IDENTITY: </span>
                  <span style={{ fontSize: '1rem', color: alert.metadata.is_unknown ? '#f87171' : '#a7f3d0', fontWeight: 800 }}>
                    {alert.metadata.display_name || alert.metadata.identity_id}
                  </span>
                </div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                  Status: <span style={{ color: alert.metadata.is_unknown ? '#f87171' : '#34d399', fontWeight: 600 }}>{alert.metadata.is_unknown ? 'UNREGISTERED' : 'VERIFIED'}</span>
                </div>
                {alert.metadata.similarity !== undefined && !alert.metadata.is_unknown && (
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                    Similarity: <span style={{ color: '#38bdf8', fontWeight: 600 }}>{(alert.metadata.similarity * 100).toFixed(1)}%</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Incident Description */}
          <div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: '4px' }}>INCIDENT TELEMETRY MESSAGE</div>
            <div style={{ backgroundColor: '#1e293b33', border: '1px solid #1e293b', borderRadius: '4px', padding: '0.65rem 0.75rem', color: '#e2e8f0', fontSize: '0.82rem' }}>
              {alert.message}
            </div>
          </div>

          {/* Audit History */}
          <div style={{ backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b', fontSize: '0.75rem' }}>
            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 700, marginBottom: '6px', textTransform: 'uppercase' }}>
              Incident Lifecycle & Audit
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', color: '#94a3b8' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Triggered UTC:</span>
                <span style={{ color: '#f1f5f9', fontFamily: 'monospace' }}>{alert.timestamp}</span>
              </div>
              {alert.acknowledged_at && (
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#60a5fa' }}>
                  <span>Acknowledged by {alert.acknowledged_by}:</span>
                  <span style={{ fontFamily: 'monospace' }}>{alert.acknowledged_at}</span>
                </div>
              )}
              {alert.resolved_at && (
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#4ade80' }}>
                  <span>Resolved by {alert.resolved_by}:</span>
                  <span style={{ fontFamily: 'monospace' }}>{alert.resolved_at}</span>
                </div>
              )}
            </div>
          </div>

          {/* Raw Metadata Details */}
          {alert.metadata && Object.keys(alert.metadata).length > 0 && (
            <div>
              <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: '4px' }}>STRUCTURED METADATA</div>
              <pre style={{ backgroundColor: '#050811', border: '1px solid #1e293b', borderRadius: '4px', padding: '0.5rem', fontSize: '0.7rem', color: '#a5f3fc', overflowX: 'auto', margin: 0 }}>
                {JSON.stringify(alert.metadata, null, 2)}
              </pre>
            </div>
          )}

          {/* Operator Action Form */}
          {alert.status === 'acknowledged' && (
            <form onSubmit={handleResolveSubmit} style={{ marginTop: '0.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                Resolution Notes / False Alarm Justification:
              </label>
              <input
                type="text"
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder="e.g. Authorized border patrol unit passing through"
                style={{
                  width: '100%',
                  backgroundColor: '#090d16',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  padding: '6px 10px',
                  borderRadius: '4px',
                  fontSize: '0.8rem',
                  boxSizing: 'border-box',
                  marginBottom: '8px',
                }}
              />
            </form>
          )}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '0.85rem 1.25rem',
            borderTop: '1px solid #1e293b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: '#1e293b33',
          }}
        >
          <button
            onClick={onClose}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              color: '#94a3b8',
              padding: '6px 12px',
              borderRadius: '5px',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close
          </button>

          <div style={{ display: 'flex', gap: '8px' }}>
            {alert.status === 'new' && (
              <button
                onClick={() => onAcknowledge(alert.alert_id)}
                disabled={isActionLoading}
                style={{
                  backgroundColor: '#2563eb',
                  border: 'none',
                  color: '#ffffff',
                  padding: '6px 14px',
                  borderRadius: '5px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Check size={14} /> Acknowledge Alert
              </button>
            )}

            {alert.status === 'acknowledged' && (
              <button
                onClick={() => onResolve(alert.alert_id, resolutionNotes)}
                disabled={isActionLoading}
                style={{
                  backgroundColor: '#16a34a',
                  border: 'none',
                  color: '#ffffff',
                  padding: '6px 14px',
                  borderRadius: '5px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <CheckCheck size={14} /> Resolve Incident
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
