import React from 'react';
import { Alert } from '../types';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import { Activity, Clock, Radio, MapPin, User, Eye } from 'lucide-react';

interface EventsPageProps {
  alerts: Alert[];
  onInspectAlert: (alert: Alert) => void;
}

export const EventsPage: React.FC<EventsPageProps> = ({ alerts, onInspectAlert }) => {
  const sortedEvents = [...alerts].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
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
            Perimeter Security Event Audit Log
          </h2>
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
            Immutable chronological audit history of spatial rule violations and operator triage
          </p>
        </div>

        <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
          Total Logged Events: <strong style={{ color: '#38bdf8' }}>{alerts.length}</strong>
        </div>
      </div>

      {/* Events Timeline List */}
      <div
        style={{
          backgroundColor: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          padding: '1.25rem',
        }}
      >
        {sortedEvents.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
            <Activity size={32} color="#334155" style={{ margin: '0 auto 8px auto' }} />
            <div>No perimeter security events logged yet.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {sortedEvents.map((evt) => (
              <div
                key={evt.alert_id}
                style={{
                  backgroundColor: '#090d16',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  padding: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                }}
              >
                {/* Timeline Marker & Type */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', flex: 1 }}>
                  <div style={{ paddingTop: '2px' }}>
                    <SeverityBadge severity={evt.severity} size="sm" />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#f8fafc' }}>
                        {evt.event_type.toUpperCase()}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                        Track #{evt.track_id} ({evt.object_class.toUpperCase()})
                      </span>
                      <StatusBadge status={evt.status} />
                    </div>

                    <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                      {evt.message}
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '0.7rem', color: '#64748b', marginTop: '2px' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#38bdf8' }}>
                        <Radio size={11} /> {evt.camera_id}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <MapPin size={11} /> {evt.zone_id || evt.tripwire_id || 'Sector Zone'}
                      </span>
                      {evt.acknowledged_by && (
                        <span style={{ color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <User size={11} /> Ack by: {evt.acknowledged_by}
                        </span>
                      )}
                      {evt.resolved_by && (
                        <span style={{ color: '#4ade80', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <User size={11} /> Resolved by: {evt.resolved_by}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right: Timestamp & Action */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#64748b', fontFamily: 'monospace' }}>
                    <Clock size={11} />
                    <span>{evt.timestamp}</span>
                  </div>

                  <button
                    onClick={() => onInspectAlert(evt)}
                    style={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      color: '#94a3b8',
                      padding: '4px 10px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <Eye size={12} /> Inspect Audit
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
