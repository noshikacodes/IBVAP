import React from 'react';
import { ThreatSeverity } from '../types';

interface SeverityBadgeProps {
  severity: ThreatSeverity | string;
  size?: 'sm' | 'md' | 'lg';
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, size = 'md' }) => {
  const sev = (severity || 'medium').toLowerCase() as ThreatSeverity;

  const styles: Record<ThreatSeverity, { bg: string; text: string; border: string; label: string }> = {
    critical: {
      bg: 'rgba(239, 68, 68, 0.15)',
      text: '#f87171',
      border: 'rgba(239, 68, 68, 0.4)',
      label: 'CRITICAL',
    },
    high: {
      bg: 'rgba(249, 115, 22, 0.15)',
      text: '#fb923c',
      border: 'rgba(249, 115, 22, 0.4)',
      label: 'HIGH',
    },
    medium: {
      bg: 'rgba(234, 179, 8, 0.15)',
      text: '#facc15',
      border: 'rgba(234, 179, 8, 0.4)',
      label: 'MEDIUM',
    },
    low: {
      bg: 'rgba(56, 189, 248, 0.15)',
      text: '#38bdf8',
      border: 'rgba(56, 189, 248, 0.4)',
      label: 'LOW',
    },
  };

  const current = styles[sev] || styles.medium;
  const padding = size === 'sm' ? '2px 6px' : size === 'lg' ? '6px 14px' : '4px 10px';
  const fontSize = size === 'sm' ? '0.7rem' : size === 'lg' ? '0.85rem' : '0.75rem';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding,
        backgroundColor: current.bg,
        color: current.text,
        border: `1px solid ${current.border}`,
        borderRadius: '4px',
        fontSize,
        fontWeight: 700,
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: current.text,
          display: 'inline-block',
        }}
      />
      {current.label}
    </span>
  );
};
