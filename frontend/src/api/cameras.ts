import { API_BASE_URL } from './config';
import { CameraStreamInfo, CameraSourceUpdateRequest, ConnectionTestResult } from '../types';

export interface CameraListApiResponse {
  total: number;
  cameras: Array<{
    camera_id: string;
    name: string;
    source_type: 'rtsp' | 'file' | 'webcam';
    source_url: string;
    enabled: boolean;
    status: 'online' | 'connecting' | 'offline' | 'reconnecting' | 'simulated';
    is_simulated?: boolean;
    location_metadata: {
      sector?: string;
      location_name?: string;
      latitude?: number;
      longitude?: number;
      resolution?: string;
      fps?: number;
      pipeline?: string;
    };
    last_event_at: string | null;
    created_at: string;
  }>;
}

export async function fetchCameras(): Promise<CameraStreamInfo[]> {
  const response = await fetch(`${API_BASE_URL}/cameras`);
  if (!response.ok) {
    throw new Error(`Failed to fetch cameras (status: ${response.status})`);
  }
  const data: CameraListApiResponse = await response.json();

  return data.cameras.map((c) => ({
    id: c.camera_id,
    name: c.name,
    sector: c.location_metadata?.sector || 'Perimeter Sector',
    location_name: c.location_metadata?.location_name || '',
    latitude: c.location_metadata?.latitude,
    longitude: c.location_metadata?.longitude,
    status: c.status,
    is_simulated: c.is_simulated !== undefined ? c.is_simulated : (c.source_type === 'file' || c.status === 'simulated'),
    enabled: c.enabled,
    source_type: c.source_type,
    source_url: c.source_url,
    video_source: c.source_url,
    resolution: c.location_metadata?.resolution || '640x480',
    fps: c.location_metadata?.fps || 15,
    last_event_time: c.last_event_at || undefined,
    active_alerts: 0,
  }));
}

export async function updateCameraStatus(
  cameraId: string,
  status: 'online' | 'connecting' | 'offline' | 'reconnecting' | 'simulated'
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/cameras/${cameraId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update camera status (status: ${response.status})`);
  }
}

export async function updateCameraSource(
  cameraId: string,
  payload: CameraSourceUpdateRequest
): Promise<CameraStreamInfo> {
  const response = await fetch(`${API_BASE_URL}/cameras/${cameraId}/source`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to update camera source (status: ${response.status})`);
  }
  const c = await response.json();
  return {
    id: c.camera_id,
    name: c.name,
    sector: c.location_metadata?.sector || 'Perimeter Sector',
    location_name: c.location_metadata?.location_name || '',
    latitude: c.location_metadata?.latitude,
    longitude: c.location_metadata?.longitude,
    status: c.status,
    is_simulated: c.is_simulated !== undefined ? c.is_simulated : (c.status === 'simulated'),
    enabled: c.enabled,
    source_type: c.source_type,
    source_url: c.source_url,
    video_source: c.source_url,
    resolution: c.location_metadata?.resolution || '640x480',
    fps: c.location_metadata?.fps || 15,
    last_event_time: c.last_event_at || undefined,
    active_alerts: 0,
  };
}

export async function testCameraConnection(
  cameraId: string,
  payload: {
    source_url: string;
    username?: string;
    password?: string;
    timeout_seconds?: number;
  }
): Promise<ConnectionTestResult> {
  const response = await fetch(`${API_BASE_URL}/cameras/${cameraId}/test-connection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to test connection (status: ${response.status})`);
  }
  return response.json();
}

export async function resetCameraDemo(cameraId: string): Promise<CameraStreamInfo> {
  const response = await fetch(`${API_BASE_URL}/cameras/${cameraId}/reset-demo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to reset demo stream (status: ${response.status})`);
  }
  const c = await response.json();
  return {
    id: c.camera_id,
    name: c.name,
    sector: c.location_metadata?.sector || 'Perimeter Sector',
    location_name: c.location_metadata?.location_name || '',
    latitude: c.location_metadata?.latitude,
    longitude: c.location_metadata?.longitude,
    status: c.status,
    is_simulated: true,
    enabled: c.enabled,
    source_type: c.source_type,
    source_url: c.source_url,
    video_source: c.source_url,
    resolution: c.location_metadata?.resolution || '640x480',
    fps: c.location_metadata?.fps || 15,
    last_event_time: c.last_event_at || undefined,
    active_alerts: 0,
  };
}
