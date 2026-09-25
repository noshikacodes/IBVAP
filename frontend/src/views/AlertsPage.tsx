import React, { useState } from 'react';
import { Alert } from '../types';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import {
  AlertTriangle,
  Search,
  Eye,
  Check,
  CheckCheck,
  Radio,
} from 'lucide-react';

interface AlertsPageProps {
  alerts: Alert[];
  onAcknowledge: (alertId: string) => void;
  onResolve: (alertId: string) => void;
  onInspect: (alert: Alert) => void;
  isActionLoading?: boolean;
}

export const AlertsPage: React.FC<AlertsPageProps> = ({
  alerts,
  onAcknowledge,
  onResolve,
  onInspect,
  isActionLoading = false,
}) => {
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [cameraFilter, setCameraFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const cameras = Array.from(new Set(alerts.map((a) => a.camera_id)));

  const filteredAlerts = alerts.filter((alt) => {
    if (severityFilter !== 'all' && alt.severity.toLowerCase() !== severityFilter.toLowerCase()) {
      return false;
    }
    if (statusFilter !== 'all' && alt.status.toLowerCase() !== statusFilter.toLowerCase()) {
      return false;
    }
    if (cameraFilter !== 'all' && alt.camera_id !== cameraFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTrack = alt.track_id.toString().includes(q);
      const matchMsg = alt.message.toLowerCase().includes(q);
      const matchType = alt.event_type.toLowerCase().includes(q);
      const matchId = alt.alert_id.toLowerCase().includes(q);
      if (!matchTrack && !matchMsg && !matchType && !matchId) {
        return false;
      }
    }
    return true;
  });

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
            Security Alert Management
          </h2>
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
            Triage, acknowledge, and resolve real-time spatial perimeter intrusion alerts
          </p>
        </div>
        <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
          Showing <span style={{ color: '#38bdf8', fontWeight: 700 }}>{filteredAlerts.length}</span> of {alerts.length} Incidents
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div
        style={{
          backgroundColor: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          padding: '0.85rem 1rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '12px',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', flex: 1 }}>
          {/* Search Box */}
          <div style={{ position: 'relative', minWidth: '220px' }}>
            <Search size={14} color="#64748b" style={{ position: 'absolute', left: '10px', top: '10px' }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by track, message, ID..."
              style={{
                width: '100%',
                backgroundColor: '#090d16',
                border: '1px solid #334155',
                color: '#f8fafc',
                padding: '6px 10px 6px 32px',
                borderRadius: '5px',
                fontSize: '0.8rem',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            style={{
              backgroundColor: '#090d16',
              border: '1px solid #334155',
              color: '#cbd5e1',
              padding: '6px 10px',
              borderRadius: '5px',
              fontSize: '0.8rem',
            }}
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              backgroundColor: '#090d16',
              border: '1px solid #334155',
              color: '#cbd5e1',
              padding: '6px 10px',
              borderRadius: '5px',
              fontSize: '0.8rem',
            }}
          >
            <option value="all">All Statuses</option>
            <option value="new">New / Unacknowledged</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </select>

          {/* Camera Filter */}
          <select
            value={cameraFilter}
            onChange={(e) => setCameraFilter(e.target.value)}
            style={{
              backgroundColor: '#090d16',
              border: '1px solid #334155',
              color: '#cbd5e1',
              padding: '6px 10px',
              borderRadius: '5px',
              fontSize: '0.8rem',
            }}
          >
            <option value="all">All Cameras</option>
            {cameras.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Clear Filters Button */}
        {(severityFilter !== 'all' || statusFilter !== 'all' || cameraFilter !== 'all' || searchQuery) && (
          <button
            onClick={() => {
              setSeverityFilter('all');
              setStatusFilter('all');
              setCameraFilter('all');
              setSearchQuery('');
            }}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              color: '#94a3b8',
              padding: '5px 10px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              cursor: 'pointer',
            }}
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Alerts Table / List */}
      <div
        style={{
          backgroundColor: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        {filteredAlerts.length === 0 ? (
          <div
            style={{
              padding: '3rem 1rem',
              textAlign: 'center',
              color: '#64748b',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <AlertTriangle size={32} color="#334155" />
            <div style={{ fontSize: '0.9rem', color: '#94a3b8' }}>No security alerts match the selected criteria</div>
            <div style={{ fontSize: '0.75rem' }}>Adjust filter parameters or inspect the live feed for new events</div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#090d16', borderBottom: '1px solid #1e293b', color: '#64748b', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  <th style={{ padding: '10px 14px' }}>Severity</th>
                  <th style={{ padding: '10px 14px' }}>Incident Type</th>
                  <th style={{ padding: '10px 14px' }}>Target</th>
                  <th style={{ padding: '10px 14px' }}>Camera</th>
                  <th style={{ padding: '10px 14px' }}>Telemetry Message</th>
                  <th style={{ padding: '10px 14px' }}>Timestamp</th>
                  <th style={{ padding: '10px 14px' }}>Status</th>
                  <th style={{ padding: '10px 14px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((alert) => (
                  <tr
                    key={alert.alert_id}
                    style={{
                      borderBottom: '1px solid #1e293b',
                      backgroundColor: alert.status === 'new' && alert.severity === 'critical' ? 'rgba(239, 68, 68, 0.05)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '10px 14px' }}>
                      <SeverityBadge severity={alert.severity} size="sm" />
                    </td>
                    <td style={{ padding: '10px 14px', fontWeight: 700, color: '#f1f5f9' }}>
                      {alert.event_type.toUpperCase()}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>
                      TRACK #{alert.track_id} ({alert.object_class.toUpperCase()})
                    </td>
                    <td style={{ padding: '10px 14px', color: '#38bdf8' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Radio size={11} /> {alert.camera_id}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px', color: '#94a3b8', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {alert.message}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#64748b', fontFamily: 'monospace', fontSize: '0.72rem' }}>
                      {new Date(alert.timestamp).toLocaleTimeString([], { hour12: false })}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <StatusBadge status={alert.status} />
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          onClick={() => onInspect(alert)}
                          title="Inspect incident details"
                          style={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            color: '#94a3b8',
                            padding: '4px 8px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.72rem',
                          }}
                        >
                          <Eye size={12} />
                        </button>

                        {alert.status === 'new' && (
                          <button
                            onClick={() => onAcknowledge(alert.alert_id)}
                            disabled={isActionLoading}
                            title="Acknowledge alert"
                            style={{
                              backgroundColor: 'rgba(59, 130, 246, 0.15)',
                              border: '1px solid #3b82f6',
                              color: '#60a5fa',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                            }}
                          >
                            <Check size={12} />
                          </button>
                        )}

                        {alert.status === 'acknowledged' && (
                          <button
                            onClick={() => onResolve(alert.alert_id)}
                            disabled={isActionLoading}
                            title="Resolve alert"
                            style={{
                              backgroundColor: 'rgba(34, 197, 94, 0.15)',
                              border: '1px solid #22c55e',
                              color: '#4ade80',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                            }}
                          >
                            <CheckCheck size={12} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
