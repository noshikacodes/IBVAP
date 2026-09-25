export type ThreatSeverity = 'critical' | 'high' | 'medium' | 'low';
export type AlertStatus = 'new' | 'acknowledged' | 'resolved';

export interface Alert {
  alert_id: string;
  event_id: string;
  event_type: string;
  severity: ThreatSeverity;
  timestamp: string;
  camera_id: string;
  track_id: number;
  object_class: string;
  zone_id: string | null;
  tripwire_id: string | null;
  position: [number, number];
  message: string;
  metadata: Record<string, any>;
  status: AlertStatus;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface AlertListResponse {
  total: number;
  alerts: Alert[];
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
}

export type TabType = 'dashboard' | 'cameras' | 'alerts' | 'incidents' | 'events' | 'settings' | 'camera-settings';

export type WebSocketStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

export interface CameraStreamInfo {
  id: string;
  name: string;
  sector: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  status: 'online' | 'connecting' | 'degraded' | 'offline' | 'reconnecting' | 'simulated';
  is_simulated: boolean;
  enabled?: boolean;
  source_type?: 'rtsp' | 'file' | 'webcam';
  source_url?: string;
  video_source: string;
  resolution: string;
  fps: number;
  last_event_time?: string;
  active_alerts: number;
  night_mode?: boolean;
  min_object_size?: number;
  transport?: string;
  reconnect_count?: number;
}

export interface ConnectionTestResult {
  camera_id?: string;
  reachable: boolean;
  status: string;
  protocol: string;
  codec?: string;
  resolution?: string;
  fps?: number;
  latency_ms?: number;
  relay_status?: string;
  hls_status?: string;
  masked_url?: string;
  error_reason?: string;
}

export interface CameraSourceUpdateRequest {
  source_type?: 'rtsp' | 'file' | 'webcam';
  source_url?: string;
  username?: string;
  password?: string;
  enabled?: boolean;
  name?: string;
  sector?: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  is_simulated?: boolean;
}

export interface CameraHealth {
  camera_id: string;
  name: string;
  connection_state: string;
  source_url: string;
  resolution: string;
  fps: number;
  reconnect_count: number;
  frames_received: number;
  last_frame_timestamp: string | null;
  last_error: string | null;
  calibration_metadata: Record<string, any>;
}

export interface PTZPosition {
  pan: number;
  tilt: number;
  zoom: number;
}

export interface PTZState {
  camera_id: string;
  connection_state: string;
  pan: number;
  tilt: number;
  zoom: number;
  driver_type: string;
  last_command_id?: string | null;
  last_command_timestamp?: string | null;
  last_command_status?: string | null;
  current_target?: {
    track_id?: number;
    event_type?: string;
    severity?: string;
    acquired_at?: string;
  } | null;
  error?: string | null;
}

export type IncidentStatus = 'open' | 'in_investigation' | 'dispatched' | 'resolved' | 'closed';

export interface IncidentEvidence {
  evidence_id: string;
  evidence_type: string;
  timestamp: string;
  camera_id: string;
  sha256_hash: string;
  data: Record<string, any>;
  uri?: string | null;
}

export interface IncidentTimelineEntry {
  entry_id: string;
  timestamp: string;
  source: string;
  severity: ThreatSeverity;
  event_type: string;
  description: string;
  camera_id?: string | null;
  details: Record<string, any>;
}

export interface AgencyDispatch {
  dispatch_id: string;
  agency: string;
  agency_name: string;
  endpoint_url: string;
  status: 'pending' | 'delivered' | 'acknowledged' | 'retrying' | 'failed';
  dispatched_at: string;
  acknowledged_at?: string | null;
  attempts: number;
  last_error?: string | null;
  ack_reference?: string | null;
  response_payload?: Record<string, any> | null;
}

export interface Incident {
  incident_id: string;
  title: string;
  severity: ThreatSeverity;
  status: IncidentStatus;
  created_at: string;
  updated_at: string;
  sector: string;
  primary_camera_id: string;
  track_ids: number[];
  description: string;
  summary: string;
  evidence_items: IncidentEvidence[];
  timeline: IncidentTimelineEntry[];
  dispatches: AgencyDispatch[];
  dossier_hash: string;
  metadata: Record<string, any>;
}

export interface IncidentListResponse {
  total: number;
  incidents: Incident[];
}



