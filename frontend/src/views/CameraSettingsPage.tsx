import React, { useState } from 'react';
import {
  Radio,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Eye,
  EyeOff,
  Save,
  RotateCcw,
  Zap,
  Activity,
  Wifi,
  Video,
} from 'lucide-react';
import { CameraStreamInfo, ConnectionTestResult } from '../types';
import {
  updateCameraSource,
  testCameraConnection,
  resetCameraDemo,
} from '../api/cameras';

interface CameraSettingsPageProps {
  cameras: CameraStreamInfo[];
  onRefresh?: () => void;
}

interface CameraFormState {
  name: string;
  sector: string;
  location_name: string;
  latitude: string;
  longitude: string;
  source_type: 'rtsp' | 'file' | 'webcam';
  source_url: string;
  username: string;
  password: string;
  enabled: boolean;
  is_simulated: boolean;
  showPassword?: boolean;
}

export const CameraSettingsPage: React.FC<CameraSettingsPageProps> = ({
  cameras,
  onRefresh,
}) => {
  // Ensure we always represent the 4 canonical slots
  const DEFAULT_SLOTS = ['CAM_01', 'CAM_02', 'CAM_03', 'CAM_04'];

  const initialForms = DEFAULT_SLOTS.reduce<Record<string, CameraFormState>>((acc, id) => {
    const cam = cameras.find((c) => c.id === id);
    acc[id] = {
      name: cam?.name || `Surveillance Camera ${id}`,
      sector: cam?.sector || 'Sector Alpha',
      location_name: cam?.location_name || '',
      latitude: cam?.latitude !== undefined ? String(cam.latitude) : '',
      longitude: cam?.longitude !== undefined ? String(cam.longitude) : '',
      source_type: cam?.source_type || 'rtsp',
      source_url: cam?.source_url || `rtsp://localhost:8554/ibvap-${id.toLowerCase().replace('_', '')}`,
      username: '',
      password: '',
      enabled: cam?.enabled !== false,
      is_simulated: cam?.is_simulated !== false,
      showPassword: false,
    };
    return acc;
  }, {});

  const [formState, setFormState] = useState<Record<string, CameraFormState>>(initialForms);
  const [testResults, setTestResults] = useState<Record<string, ConnectionTestResult | null>>({});
  const [testingSlots, setTestingSlots] = useState<Record<string, boolean>>({});
  const [savingSlots, setSavingSlots] = useState<Record<string, boolean>>({});
  const [messages, setMessages] = useState<Record<string, { type: 'success' | 'error'; text: string } | null>>({});

  const handleFieldChange = (id: string, field: keyof CameraFormState, value: any) => {
    setFormState((prev) => ({
      ...prev,
      [id]: {
        ...prev[id],
        [field]: value,
      },
    }));
  };

  // Test Connection Action
  const handleTestConnection = async (id: string) => {
    const form = formState[id];
    setTestingSlots((prev) => ({ ...prev, [id]: true }));
    setMessages((prev) => ({ ...prev, [id]: null }));

    try {
      const result = await testCameraConnection(id, {
        source_url: form.source_url,
        username: form.username.trim() || undefined,
        password: form.password || undefined,
        timeout_seconds: 3.0,
      });

      setTestResults((prev) => ({ ...prev, [id]: result }));

      if (result.reachable) {
        setMessages((prev) => ({
          ...prev,
          [id]: {
            type: 'success',
            text: `RTSP stream reachable (${result.resolution || 'HD'} @ ${result.fps || 30} FPS, latency ${result.latency_ms || 0}ms)`,
          },
        }));
      } else {
        setMessages((prev) => ({
          ...prev,
          [id]: {
            type: 'error',
            text: `Connection failed: ${result.error_reason || 'RTSP host unreachable'}`,
          },
        }));
      }
    } catch (err: any) {
      setMessages((prev) => ({
        ...prev,
        [id]: { type: 'error', text: err.message || 'Connection test error' },
      }));
    } finally {
      setTestingSlots((prev) => ({ ...prev, [id]: false }));
    }
  };

  // Save Configuration Action
  const handleSaveConfiguration = async (id: string) => {
    const form = formState[id];
    setSavingSlots((prev) => ({ ...prev, [id]: true }));
    setMessages((prev) => ({ ...prev, [id]: null }));

    try {
      await updateCameraSource(id, {
        name: form.name,
        sector: form.sector,
        location_name: form.location_name,
        latitude: form.latitude ? parseFloat(form.latitude) : undefined,
        longitude: form.longitude ? parseFloat(form.longitude) : undefined,
        source_type: form.source_type,
        source_url: form.source_url,
        username: form.username.trim() || undefined,
        password: form.password || undefined,
        enabled: form.enabled,
        is_simulated: form.is_simulated,
      });

      setMessages((prev) => ({
        ...prev,
        [id]: {
          type: 'success',
          text: form.is_simulated
            ? 'Simulated demo stream configuration saved and active.'
            : 'Real RTSP camera configured and relayed to C2 surveillance matrix.',
        },
      }));

      if (onRefresh) onRefresh();
    } catch (err: any) {
      setMessages((prev) => ({
        ...prev,
        [id]: { type: 'error', text: err.message || 'Failed to save configuration' },
      }));
    } finally {
      setSavingSlots((prev) => ({ ...prev, [id]: false }));
    }
  };

  // Reset to Demo Action
  const handleResetDemo = async (id: string) => {
    setSavingSlots((prev) => ({ ...prev, [id]: true }));
    setMessages((prev) => ({ ...prev, [id]: null }));

    try {
      const updated = await resetCameraDemo(id);
      setFormState((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          source_url: updated.source_url || `rtsp://localhost:8554/ibvap-${id.toLowerCase().replace('_', '')}`,
          is_simulated: true,
          username: '',
          password: '',
        },
      }));

      setTestResults((prev) => ({ ...prev, [id]: null }));
      setMessages((prev) => ({
        ...prev,
        [id]: { type: 'success', text: 'Reset slot to default synthetic demo stream.' },
      }));

      if (onRefresh) onRefresh();
    } catch (err: any) {
      setMessages((prev) => ({
        ...prev,
        [id]: { type: 'error', text: err.message || 'Failed to reset demo stream' },
      }));
    } finally {
      setSavingSlots((prev) => ({ ...prev, [id]: false }));
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.5rem',
          paddingBottom: '1rem',
          borderBottom: '1px solid #1e293b',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <div
              style={{
                backgroundColor: '#2563eb22',
                border: '1px solid #2563eb66',
                padding: '6px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Sliders size={22} color="#38bdf8" />
            </div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '0.02em', margin: 0, color: '#f8fafc' }}>
              Camera & Stream Settings
            </h1>
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>
            Configure video ingestion sources per camera slot. Connect real IP/RTSP cameras, mobile RTSP streams, or switch to simulated border surveillance footage.
          </p>
        </div>

        <button
          onClick={() => {
            if (onRefresh) onRefresh();
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 16px',
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '6px',
            color: '#f8fafc',
            fontSize: '0.8rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'background-color 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#334155')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#1e293b')}
        >
          <RefreshCw size={14} />
          Reload Slots
        </button>
      </div>

      {/* 4 Camera Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(620px, 1fr))',
          gap: '1.5rem',
        }}
      >
        {DEFAULT_SLOTS.map((slotId) => {
          const form = formState[slotId];
          const isTesting = testingSlots[slotId] || false;
          const isSaving = savingSlots[slotId] || false;
          const testRes = testResults[slotId];
          const msg = messages[slotId];

          const isSimulated = form.is_simulated;
          const isEnabled = form.enabled;

          return (
            <div
              key={slotId}
              id={`camera-card-${slotId}`}
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '10px',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
              }}
            >
              {/* Card Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  paddingBottom: '0.75rem',
                  borderBottom: '1px solid #1e293b',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span
                    style={{
                      backgroundColor: '#1e293b',
                      color: '#38bdf8',
                      fontFamily: 'monospace',
                      fontWeight: 800,
                      fontSize: '0.85rem',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      border: '1px solid #334155',
                    }}
                  >
                    {slotId}
                  </span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#f8fafc' }}>
                      {form.name || `Camera ${slotId}`}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      {form.sector || 'Sector Alpha'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {/* Source Mode Badge */}
                  <span
                    style={{
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '4px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      backgroundColor: isSimulated ? 'rgba(168, 85, 247, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                      color: isSimulated ? '#c084fc' : '#34d399',
                      border: `1px solid ${isSimulated ? '#a855f744' : '#10b98144'}`,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    {isSimulated ? <Radio size={12} /> : <Wifi size={12} />}
                    {isSimulated ? 'SIMULATED / DEMO' : 'REAL IP CAMERA'}
                  </span>

                  {/* Enable Switch */}
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      color: isEnabled ? '#10b981' : '#64748b',
                      fontWeight: 600,
                      backgroundColor: '#1e293b',
                      padding: '3px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      onChange={(e) => handleFieldChange(slotId, 'enabled', e.target.checked)}
                      style={{ cursor: 'pointer' }}
                    />
                    {isEnabled ? 'ENABLED' : 'DISABLED'}
                  </label>
                </div>
              </div>

              {/* Form Body */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {/* Camera Name */}
                <div style={{ gridColumn: 'span 1' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                    Camera Name
                  </label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => handleFieldChange(slotId, 'name', e.target.value)}
                    placeholder="e.g. Sector Alpha - North Gate"
                    style={{
                      width: '100%',
                      backgroundColor: '#090d16',
                      border: '1px solid #334155',
                      borderRadius: '6px',
                      padding: '8px 10px',
                      color: '#f8fafc',
                      fontSize: '0.82rem',
                    }}
                  />
                </div>

                {/* Sector / Location */}
                <div style={{ gridColumn: 'span 1' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                    Sector / Area
                  </label>
                  <input
                    type="text"
                    value={form.sector}
                    onChange={(e) => handleFieldChange(slotId, 'sector', e.target.value)}
                    placeholder="e.g. Sector Alpha"
                    style={{
                      width: '100%',
                      backgroundColor: '#090d16',
                      border: '1px solid #334155',
                      borderRadius: '6px',
                      padding: '8px 10px',
                      color: '#f8fafc',
                      fontSize: '0.82rem',
                    }}
                  />
                </div>

                {/* Location Name & GPS Coordinates */}
                <div style={{ gridColumn: 'span 2', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                      Location Description / Checkpoint
                    </label>
                    <input
                      type="text"
                      value={form.location_name}
                      onChange={(e) => handleFieldChange(slotId, 'location_name', e.target.value)}
                      placeholder="e.g. Checkpost Barrier 01"
                      style={{
                        width: '100%',
                        backgroundColor: '#090d16',
                        border: '1px solid #334155',
                        borderRadius: '6px',
                        padding: '8px 10px',
                        color: '#f8fafc',
                        fontSize: '0.82rem',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                      Latitude
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={form.latitude}
                      onChange={(e) => handleFieldChange(slotId, 'latitude', e.target.value)}
                      placeholder="34.0522"
                      style={{
                        width: '100%',
                        backgroundColor: '#090d16',
                        border: '1px solid #334155',
                        borderRadius: '6px',
                        padding: '8px 10px',
                        color: '#f8fafc',
                        fontSize: '0.82rem',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                      Longitude
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={form.longitude}
                      onChange={(e) => handleFieldChange(slotId, 'longitude', e.target.value)}
                      placeholder="-118.2437"
                      style={{
                        width: '100%',
                        backgroundColor: '#090d16',
                        border: '1px solid #334155',
                        borderRadius: '6px',
                        padding: '8px 10px',
                        color: '#f8fafc',
                        fontSize: '0.82rem',
                      }}
                    />
                  </div>
                </div>

                {/* Source Mode Selector */}
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                    Stream Ingestion Mode
                  </label>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                      type="button"
                      onClick={() => handleFieldChange(slotId, 'is_simulated', true)}
                      style={{
                        flex: 1,
                        padding: '10px',
                        borderRadius: '6px',
                        border: isSimulated ? '2px solid #a855f7' : '1px solid #334155',
                        backgroundColor: isSimulated ? '#1e1b4b' : '#090d16',
                        color: isSimulated ? '#e9d5ff' : '#94a3b8',
                        fontWeight: 600,
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                      }}
                    >
                      <Radio size={16} />
                      SIMULATED / DEMO
                    </button>
                    <button
                      type="button"
                      onClick={() => handleFieldChange(slotId, 'is_simulated', false)}
                      style={{
                        flex: 1,
                        padding: '10px',
                        borderRadius: '6px',
                        border: !isSimulated ? '2px solid #10b981' : '1px solid #334155',
                        backgroundColor: !isSimulated ? '#064e3b' : '#090d16',
                        color: !isSimulated ? '#a7f3d0' : '#94a3b8',
                        fontWeight: 600,
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                      }}
                    >
                      <Video size={16} />
                      RTSP / IP CAMERA
                    </button>
                  </div>
                </div>

                {/* RTSP Stream Configuration Fields (Enabled when Real Camera is active) */}
                <div
                  style={{
                    gridColumn: 'span 2',
                    backgroundColor: isSimulated ? 'rgba(30, 41, 59, 0.3)' : 'rgba(15, 23, 42, 0.8)',
                    border: `1px solid ${isSimulated ? '#1e293b' : '#334155'}`,
                    borderRadius: '8px',
                    padding: '1rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.75rem',
                  }}
                >
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                      RTSP Stream URL {isSimulated && <span style={{ color: '#64748b' }}>(Auto-managed in simulated mode)</span>}
                    </label>
                    <input
                      type="text"
                      disabled={isSimulated}
                      value={form.source_url}
                      onChange={(e) => handleFieldChange(slotId, 'source_url', e.target.value)}
                      placeholder="rtsp://192.168.1.101:8554/live"
                      style={{
                        width: '100%',
                        backgroundColor: isSimulated ? '#0f172a' : '#090d16',
                        border: '1px solid #334155',
                        borderRadius: '6px',
                        padding: '8px 10px',
                        color: isSimulated ? '#64748b' : '#38bdf8',
                        fontFamily: 'monospace',
                        fontSize: '0.8rem',
                        opacity: isSimulated ? 0.7 : 1,
                      }}
                    />
                    {!isSimulated && (
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '6px', backgroundColor: '#090d16', padding: '8px 10px', borderRadius: '4px', border: '1px solid #1e293b', lineHeight: 1.45 }}>
                        <div style={{ color: '#f87171', fontWeight: 600 }}>
                          ⚠️ Do NOT enter: <code style={{ color: '#fca5a5' }}>http://PHONE_IP:8080</code> (that is the web UI, not RTSP).
                        </div>
                        <div style={{ marginTop: '3px', color: '#cbd5e1' }}>
                          📱 For <strong>IP Webcam</strong> app, try: <code style={{ color: '#38bdf8' }}>rtsp://PHONE_IP:8080/h264_pcm.sdp</code> or <code style={{ color: '#38bdf8' }}>rtsp://PHONE_IP:8080/h264_ulaw.sdp</code>
                        </div>
                        <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '3px' }}>
                          💡 Verify your exact RTSP stream URL in the IP Webcam app under <em>"Video and audio"</em> / streaming URL info.
                        </div>
                      </div>
                    )}
                  </div>

                  {!isSimulated && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                          Username (Optional)
                        </label>
                        <input
                          type="text"
                          value={form.username}
                          onChange={(e) => handleFieldChange(slotId, 'username', e.target.value)}
                          placeholder="admin"
                          style={{
                            width: '100%',
                            backgroundColor: '#090d16',
                            border: '1px solid #334155',
                            borderRadius: '6px',
                            padding: '8px 10px',
                            color: '#f8fafc',
                            fontSize: '0.82rem',
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                          Password (Optional)
                        </label>
                        <div style={{ position: 'relative' }}>
                          <input
                            type={form.showPassword ? 'text' : 'password'}
                            value={form.password}
                            onChange={(e) => handleFieldChange(slotId, 'password', e.target.value)}
                            placeholder="••••••••"
                            style={{
                              width: '100%',
                              backgroundColor: '#090d16',
                              border: '1px solid #334155',
                              borderRadius: '6px',
                              padding: '8px 36px 8px 10px',
                              color: '#f8fafc',
                              fontSize: '0.82rem',
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => handleFieldChange(slotId, 'showPassword', !form.showPassword)}
                            style={{
                              position: 'absolute',
                              right: '8px',
                              top: '50%',
                              transform: 'translateY(-50%)',
                              background: 'none',
                              border: 'none',
                              color: '#64748b',
                              cursor: 'pointer',
                            }}
                          >
                            {form.showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  <div style={{ fontSize: '0.72rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Activity size={12} />
                    Local In-Browser HLS Endpoint:
                    <span style={{ color: '#38bdf8', fontFamily: 'monospace' }}>
                      http://127.0.0.1:8888/ibvap-{slotId.toLowerCase().replace('_', '')}/index.m3u8
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Message */}
              {msg && (
                <div
                  style={{
                    backgroundColor: msg.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    border: `1px solid ${msg.type === 'success' ? '#10b981' : '#ef4444'}`,
                    borderRadius: '6px',
                    padding: '8px 12px',
                    fontSize: '0.78rem',
                    color: msg.type === 'success' ? '#34d399' : '#f87171',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  {msg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  {msg.text}
                </div>
              )}

              {/* Connection Diagnostics HUD */}
              {testRes && (
                <div
                  style={{
                    backgroundColor: '#020617',
                    border: `1px solid ${testRes.reachable ? '#1e293b' : '#7f1d1d'}`,
                    borderRadius: '6px',
                    padding: '10px',
                    fontFamily: 'monospace',
                    fontSize: '0.72rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                    <div>
                      <span style={{ color: '#64748b' }}>STATUS: </span>
                      <span style={{ color: testRes.reachable ? '#10b981' : '#ef4444', fontWeight: 700 }}>
                        {testRes.status.toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>REACHABILITY: </span>
                      <span style={{ color: testRes.reachable ? '#10b981' : '#ef4444', fontWeight: 700 }}>
                        {testRes.reachable ? 'REACHABLE' : 'UNREACHABLE'}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>RESOLUTION: </span>
                      <span style={{ color: '#f8fafc' }}>{testRes.resolution || 'N/A'}</span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>FPS: </span>
                      <span style={{ color: '#f8fafc' }}>{testRes.fps || 'N/A'}</span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>LATENCY: </span>
                      <span style={{ color: '#38bdf8' }}>{testRes.latency_ms ? `${testRes.latency_ms} ms` : 'N/A'}</span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>CODEC: </span>
                      <span style={{ color: '#f8fafc' }}>{testRes.codec || (testRes.reachable ? 'H.264' : 'N/A')}</span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>RELAY: </span>
                      <span style={{ color: testRes.reachable ? '#10b981' : '#64748b' }}>
                        {testRes.relay_status || (testRes.reachable ? 'ACTIVE' : 'STANDBY')}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>HLS: </span>
                      <span style={{ color: testRes.reachable ? '#10b981' : '#64748b' }}>
                        {testRes.hls_status || (testRes.reachable ? 'READY' : 'STANDBY')}
                      </span>
                    </div>
                  </div>

                  <div style={{ borderTop: '1px solid #1e293b', paddingTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div>
                      <span style={{ color: '#64748b' }}>SOURCE URL: </span>
                      <span style={{ color: '#38bdf8' }}>
                        {testRes.masked_url || form.source_url}
                      </span>
                    </div>
                    {testRes.error_reason && (
                      <div>
                        <span style={{ color: '#ef4444', fontWeight: 700 }}>LAST ERROR: </span>
                        <span style={{ color: '#fca5a5' }}>
                          {testRes.error_reason}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  paddingTop: '0.75rem',
                  borderTop: '1px solid #1e293b',
                  gap: '8px',
                }}
              >
                <button
                  type="button"
                  onClick={() => handleResetDemo(slotId)}
                  disabled={isSaving || isTesting}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 12px',
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '6px',
                    color: '#94a3b8',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  <RotateCcw size={14} />
                  RESET TO DEMO
                </button>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => handleTestConnection(slotId)}
                    disabled={isTesting || isSaving}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 14px',
                      backgroundColor: '#0284c7',
                      border: 'none',
                      borderRadius: '6px',
                      color: '#ffffff',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      opacity: isTesting ? 0.7 : 1,
                    }}
                  >
                    <Zap size={14} />
                    {isTesting ? 'TESTING...' : 'TEST CONNECTION'}
                  </button>

                  <button
                    type="button"
                    onClick={() => handleSaveConfiguration(slotId)}
                    disabled={isSaving || isTesting}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 16px',
                      backgroundColor: '#16a34a',
                      border: 'none',
                      borderRadius: '6px',
                      color: '#ffffff',
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      opacity: isSaving ? 0.7 : 1,
                    }}
                  >
                    <Save size={14} />
                    {isSaving ? 'SAVING...' : 'SAVE CONFIGURATION'}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
