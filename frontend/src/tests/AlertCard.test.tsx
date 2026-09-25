import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AlertCard } from '../components/AlertCard';
import { Alert } from '../types';

const mockAlert: Alert = {
  alert_id: 'alt_test_123',
  event_id: 'evt_test_123',
  event_type: 'intrusion',
  severity: 'critical',
  timestamp: '2026-08-29T12:00:00Z',
  camera_id: 'CAM_NORTH_01',
  track_id: 17,
  object_class: 'person',
  zone_id: 'zone_restricted',
  tripwire_id: null,
  position: [100.0, 200.0],
  message: 'Person breached perimeter fence',
  metadata: {},
  status: 'new',
  acknowledged_at: null,
  acknowledged_by: null,
  resolved_at: null,
  resolved_by: null,
};

describe('AlertCard Component', () => {
  it('renders alert details correctly', () => {
    render(
      <AlertCard
        alert={mockAlert}
        onAcknowledge={vi.fn()}
        onResolve={vi.fn()}
        onInspect={vi.fn()}
      />
    );

    expect(screen.getByText('INTRUSION')).toBeDefined();
    expect(screen.getByText(/CAM_NORTH_01/)).toBeDefined();
    expect(screen.getByText(/TRACK #17/)).toBeDefined();
    expect(screen.getByText('Person breached perimeter fence')).toBeDefined();
    expect(screen.getByText('Acknowledge')).toBeDefined();
  });

  it('triggers acknowledge action when clicked', () => {
    const handleAck = vi.fn();
    render(
      <AlertCard
        alert={mockAlert}
        onAcknowledge={handleAck}
        onResolve={vi.fn()}
        onInspect={vi.fn()}
      />
    );

    const ackButton = screen.getByText('Acknowledge');
    fireEvent.click(ackButton);
    expect(handleAck).toHaveBeenCalledWith('alt_test_123');
  });

  it('renders resolve button for acknowledged alerts', () => {
    const ackAlert = { ...mockAlert, status: 'acknowledged' as const };
    const handleResolve = vi.fn();

    render(
      <AlertCard
        alert={ackAlert}
        onAcknowledge={vi.fn()}
        onResolve={handleResolve}
        onInspect={vi.fn()}
      />
    );

    const resolveBtn = screen.getByText('Resolve');
    fireEvent.click(resolveBtn);
    expect(handleResolve).toHaveBeenCalledWith('alt_test_123');
  });
});
