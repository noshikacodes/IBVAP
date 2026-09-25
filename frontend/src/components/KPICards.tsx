import React from 'react';
import { Video, ShieldAlert, AlertTriangle, Users } from 'lucide-react';

interface KPICardsProps {
  totalCameras: number;
  simulatedCameras: number;
  liveCameras?: number;
  totalAlerts: number;
  newAlerts: number;
  criticalAlerts: number;
  uniqueViolatorsCount: number;
}

export const KPICards: React.FC<KPICardsProps> = ({
  totalCameras,
  simulatedCameras,
  liveCameras,
  totalAlerts,
  newAlerts,
  criticalAlerts,
  uniqueViolatorsCount,
}) => {
  const liveCount = liveCameras !== undefined ? liveCameras : Math.max(0, totalCameras - simulatedCameras);
  const cameraSubtext =
    liveCount > 0
      ? `${liveCount} Live RTSP • ${simulatedCameras} Simulated / Demo Feeds`
      : `${simulatedCameras} Simulated / Demo Feeds (0 Live RTSP)`;

  const cards = [
    {
      title: 'SURVEILLANCE CAMERAS',
      value: totalCameras,
      subtext: cameraSubtext,
      icon: <Video size={20} color="#38bdf8" />,
      borderColor: '#0284c7',
    },
    {
      title: 'ACTIVE VIOLATORS',
      value: uniqueViolatorsCount,
      subtext: liveCount > 0 ? 'Live Stream Detected Entities' : 'Tracked Entities with Infringements',
      icon: <Users size={20} color="#a855f7" />,
      borderColor: '#9333ea',
    },
    {
      title: 'TOTAL SECURITY ALERTS',
      value: totalAlerts,
      subtext: `${newAlerts} Pending Acknowledgment (${totalAlerts === 0 ? 'No System Alerts' : 'Live Ingestion Bus'})`,
      icon: <AlertTriangle size={20} color="#f59e0b" />,
      borderColor: '#d97706',
    },
    {
      title: 'CRITICAL THREATS',
      value: criticalAlerts,
      subtext: 'Immediate Operator Triage Required',
      icon: <ShieldAlert size={20} color="#ef4444" />,
      borderColor: '#dc2626',
      highlight: criticalAlerts > 0,
    },
  ];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1rem',
        marginBottom: '1.5rem',
      }}
    >
      {cards.map((c, idx) => (
        <div
          key={idx}
          style={{
            backgroundColor: '#0f172a',
            border: `1px solid ${c.highlight ? c.borderColor : '#1e293b'}`,
            borderRadius: '8px',
            padding: '1.1rem 1.25rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            boxShadow: c.highlight ? '0 0 15px rgba(239, 68, 68, 0.15)' : 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em', color: '#64748b' }}>
              {c.title}
            </span>
            <div
              style={{
                backgroundColor: 'rgba(30, 41, 59, 0.7)',
                padding: '6px',
                borderRadius: '6px',
                display: 'flex',
              }}
            >
              {c.icon}
            </div>
          </div>
          <div>
            <div
              style={{
                fontSize: '1.8rem',
                fontWeight: 800,
                color: c.highlight ? '#f87171' : '#f8fafc',
                lineHeight: 1.1,
                marginBottom: '4px',
              }}
            >
              {c.value}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{c.subtext}</div>
          </div>
        </div>
      ))}
    </div>
  );
};
