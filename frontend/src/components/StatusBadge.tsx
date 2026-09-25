import React from 'react';
import { AlertStatus } from '../types';

interface StatusBadgeProps {
  status: AlertStatus | string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const st = (status || 'new').toLowerCase() as AlertStatus;

  const styles: Record<AlertStatus, { bg: string; text: string; border: string; label: string }> = {
    new: {
      bg: 'rgba(239, 68, 68, 0.12)',
      text: '#ef4444',
      border: 'rgba(239, 68, 68, 0.3)',
      label: 'NEW',
    },
    acknowledged: {
      bg: 'rgba(59, 130, 246, 0.12)',
      text: '#60a5fa',
      border: 'rgba(59, 130, 246, 0.3)',
      label: 'ACKNOWLEDGED',
    },
    resolved: {
      bg: 'rgba(34, 197, 94, 0.12)',
      text: '#4ade80',
      border: 'rgba(34, 197, 94, 0.3)',
      label: 'RESOLVED',
    },
  };

  const current = styles[st] || styles.new;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: '2px 8px',
        backgroundColor: current.bg,
        color: current.text,
        border: `1px solid ${current.border}`,
        borderRadius: '3px',
        fontSize: '0.72rem',
        fontWeight: 600,
        textTransform: 'uppercase',
      }}
    >
      {current.label}
    </span>
  );
};
