import React from 'react';
import { HealthResponse } from '../types';
import { Server, Shield, Database } from 'lucide-react';
import { API_BASE_URL, WS_BASE_URL } from '../api/config';

interface SettingsPageProps {
  health: HealthResponse | null;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ health }) => {
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
            C2 Platform Configuration
          </h2>
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
            System environment parameters, AI vision policies, and service bus topology
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.25rem' }}>
        {/* Service Gateway Health */}
        <div
          style={{
            backgroundColor: '#0f172a',
            border: '1px solid #1e293b',
            borderRadius: '8px',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', color: '#38bdf8' }}>
            <Server size={18} />
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f8fafc' }}>Core API & Gateway</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1e293b', paddingBottom: '6px' }}>
              <span style={{ color: '#64748b' }}>REST API Base URL:</span>
              <span style={{ color: '#f8fafc', fontFamily: 'monospace' }}>{API_BASE_URL}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1e293b', paddingBottom: '6px' }}>
              <span style={{ color: '#64748b' }}>WebSocket Live URL:</span>
              <span style={{ color: '#f8fafc', fontFamily: 'monospace' }}>{WS_BASE_URL}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1e293b', paddingBottom: '6px' }}>
              <span style={{ color: '#64748b' }}>Platform Version:</span>
              <span style={{ color: '#4ade80', fontWeight: 600 }}>{health?.version || '0.1.0'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>Environment Mode:</span>
              <span style={{ color: '#cbd5e1', textTransform: 'capitalize' }}>{health?.environment || 'development'}</span>
            </div>
          </div>
        </div>

        {/* Priority Mapping Policies */}
        <div
          style={{
            backgroundColor: '#0f172a',
            border: '1px solid #1e293b',
            borderRadius: '8px',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', color: '#f59e0b' }}>
            <Shield size={18} />
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f8fafc' }}>Alert Severity Policy Matrix</span>
          </div>

          <table style={{ width: '100%', fontSize: '0.78rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b', color: '#64748b', textAlign: 'left' }}>
                <th style={{ paddingBottom: '6px' }}>Spatial Rule Event</th>
                <th style={{ paddingBottom: '6px', textAlign: 'right' }}>Assigned Severity</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #1e293b11' }}>
                <td style={{ padding: '6px 0', color: '#f1f5f9' }}>INTRUSION (Zone Breach)</td>
                <td style={{ padding: '6px 0', textAlign: 'right', color: '#ef4444', fontWeight: 700 }}>CRITICAL</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #1e293b11' }}>
                <td style={{ padding: '6px 0', color: '#f1f5f9' }}>TRIPWIRE_CROSSING</td>
                <td style={{ padding: '6px 0', textAlign: 'right', color: '#f97316', fontWeight: 700 }}>HIGH</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #1e293b11' }}>
                <td style={{ padding: '6px 0', color: '#f1f5f9' }}>LOITERING (Duration Breach)</td>
                <td style={{ padding: '6px 0', textAlign: 'right', color: '#eab308', fontWeight: 700 }}>MEDIUM</td>
              </tr>
              <tr>
                <td style={{ padding: '6px 0', color: '#f1f5f9' }}>ZONE_EXIT</td>
                <td style={{ padding: '6px 0', textAlign: 'right', color: '#38bdf8', fontWeight: 700 }}>LOW</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Messaging & Redis Transport */}
        <div
          style={{
            backgroundColor: '#0f172a',
            border: '1px solid #1e293b',
            borderRadius: '8px',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', color: '#a855f7' }}>
            <Database size={18} />
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f8fafc' }}>Messaging & Event Bus</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1e293b', paddingBottom: '6px' }}>
              <span style={{ color: '#64748b' }}>Redis Channel:</span>
              <span style={{ color: '#f8fafc', fontFamily: 'monospace' }}>ibvap.alerts</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1e293b', paddingBottom: '6px' }}>
              <span style={{ color: '#64748b' }}>Alert Deduplication Cooldown:</span>
              <span style={{ color: '#f8fafc' }}>15.0 - 30.0 seconds</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>In-Memory Capacity:</span>
              <span style={{ color: '#f8fafc' }}>1,000 Recent Alerts</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
