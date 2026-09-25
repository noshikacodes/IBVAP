import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AlertWebSocketClient } from '../api/websocket';
import { Alert } from '../types';

describe('AlertWebSocketClient', () => {
  let client: AlertWebSocketClient;

  beforeEach(() => {
    client = new AlertWebSocketClient('ws://localhost:8000/api/v1/ws/alerts');
  });

  it('initializes with disconnected status', () => {
    expect(client.status).toBe('disconnected');
  });

  it('notifies status listeners on status change', () => {
    const statusListener = vi.fn();
    client.onStatusChange(statusListener);

    // Initial status call
    expect(statusListener).toHaveBeenCalledWith('disconnected');
  });

  it('dispatches alert to registered listeners', () => {
    const alertListener = vi.fn();
    client.onAlert(alertListener);

    const testAlert: Alert = {
      alert_id: 'alt_ws_01',
      event_id: 'evt_01',
      event_type: 'intrusion',
      severity: 'critical',
      timestamp: '2026-08-29T12:00:00Z',
      camera_id: 'CAM_01',
      track_id: 1,
      object_class: 'person',
      zone_id: 'zone_1',
      tripwire_id: null,
      position: [0, 0],
      message: 'Breach',
      metadata: {},
      status: 'new',
      acknowledged_at: null,
      acknowledged_by: null,
      resolved_at: null,
      resolved_by: null,
    };

    // Trigger internal notification helper
    (client as any).notifyAlert(testAlert);

    expect(alertListener).toHaveBeenCalledWith(testAlert);
  });
});
