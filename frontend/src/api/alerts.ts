import { API_BASE_URL } from './config';
import { Alert, AlertListResponse, AlertStatus, ThreatSeverity } from '../types';

export interface FetchAlertsParams {
  camera_id?: string;
  severity?: ThreatSeverity;
  status?: AlertStatus;
  limit?: number;
  offset?: number;
}

export async function fetchAlerts(params: FetchAlertsParams = {}): Promise<AlertListResponse> {
  const query = new URLSearchParams();
  if (params.camera_id) query.append('camera_id', params.camera_id);
  if (params.severity) query.append('severity', params.severity);
  if (params.status) query.append('status', params.status);
  if (params.limit !== undefined) query.append('limit', params.limit.toString());
  if (params.offset !== undefined) query.append('offset', params.offset.toString());

  const url = `${API_BASE_URL}/alerts${query.toString() ? `?${query.toString()}` : ''}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch alerts (status: ${response.status})`);
  }
  return response.json();
}

export async function fetchAlertById(alertId: string): Promise<Alert> {
  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch alert ${alertId} (status: ${response.status})`);
  }
  return response.json();
}

export async function acknowledgeAlert(alertId: string, operatorId: string = 'operator_c2'): Promise<Alert> {
  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId }),
  });
  if (!response.ok) {
    throw new Error(`Failed to acknowledge alert ${alertId} (status: ${response.status})`);
  }
  return response.json();
}

export async function resolveAlert(
  alertId: string,
  operatorId: string = 'operator_c2',
  resolutionNotes?: string
): Promise<Alert> {
  const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      operator_id: operatorId,
      resolution_notes: resolutionNotes || 'Resolved from Command & Control Dashboard',
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to resolve alert ${alertId} (status: ${response.status})`);
  }
  return response.json();
}
