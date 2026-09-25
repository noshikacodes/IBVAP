import React from 'react';
import {
  LayoutDashboard,
  Video,
  AlertTriangle,
  FileText,
  Activity,
  Settings,
  Shield,
  Radio,
  Sliders,
} from 'lucide-react';
import { TabType } from '../types';

interface SidebarProps {
  currentTab: TabType;
  onSelectTab: (tab: TabType) => void;
  newAlertCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  newAlertCount,
}) => {
  const navItems: { id: TabType; label: string; icon: React.ReactNode; badge?: number }[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <LayoutDashboard size={18} />,
    },
    {
      id: 'cameras',
      label: 'Surveillance Grid',
      icon: <Video size={18} />,
    },
    {
      id: 'camera-settings',
      label: 'Camera Settings',
      icon: <Sliders size={18} />,
    },
    {
      id: 'alerts',
      label: 'Security Alerts',
      icon: <AlertTriangle size={18} />,
      badge: newAlertCount,
    },
    {
      id: 'incidents',
      label: 'Tactical Incidents',
      icon: <FileText size={18} />,
    },
    {
      id: 'events',
      label: 'Event Audit Log',
      icon: <Activity size={18} />,
    },
    {
      id: 'settings',
      label: 'System Settings',
      icon: <Settings size={18} />,
    },
  ];


  return (
    <aside
      style={{
        width: '240px',
        backgroundColor: '#0f172a',
        borderRight: '1px solid #1e293b',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
        flexShrink: 0,
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: '1.25rem 1rem',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <div
          style={{
            backgroundColor: '#2563eb',
            padding: '6px',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Shield size={20} color="#ffffff" />
        </div>
        <div>
          <div style={{ fontWeight: 800, fontSize: '1rem', letterSpacing: '0.05em', color: '#f8fafc' }}>
            IBVAP C2
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b', letterSpacing: '0.02em' }}>
            Border Analytics v0.1.0
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <nav style={{ padding: '1rem 0.5rem', display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
        <div style={{ padding: '0 0.5rem 0.5rem', fontSize: '0.68rem', fontWeight: 700, color: '#475569', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          Operations
        </div>
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.65rem 0.75rem',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: isActive ? '#1e293b' : 'transparent',
                color: isActive ? '#38bdf8' : '#94a3b8',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.85rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                textAlign: 'left',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = '#1e293b55';
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ color: isActive ? '#38bdf8' : '#64748b' }}>{item.icon}</span>
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 ? (
                <span
                  style={{
                    backgroundColor: '#ef4444',
                    color: '#ffffff',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: '10px',
                    minWidth: '18px',
                    textAlign: 'center',
                  }}
                >
                  {item.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </nav>

      {/* Footer / Telemetry Status */}
      <div
        style={{
          padding: '1rem',
          borderTop: '1px solid #1e293b',
          backgroundColor: '#090d16',
          fontSize: '0.72rem',
          color: '#64748b',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
          <Radio size={12} color="#10b981" />
          <span style={{ color: '#94a3b8', fontWeight: 600 }}>C2 Engine Core</span>
        </div>
        <div>Sector Patrol Mode • Active</div>
      </div>
    </aside>
  );
};
