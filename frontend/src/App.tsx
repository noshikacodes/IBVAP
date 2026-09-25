import React, { useState, useEffect, useCallback } from 'react';
import { Alert, TabType, WebSocketStatus, HealthResponse, CameraStreamInfo } from './types';
import { fetchAlerts, acknowledgeAlert, resolveAlert } from './api/alerts';
import { fetchCameras } from './api/cameras';
import { fetchHealth } from './api/health';
import { alertWsClient } from './api/websocket';

import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { AlertDetailModal } from './components/AlertDetailModal';
import { DashboardHome } from './views/DashboardHome';
import { AlertsPage } from './views/AlertsPage';
import { CamerasPage } from './views/CamerasPage';
import { IncidentsPage } from './views/IncidentsPage';
import { EventsPage } from './views/EventsPage';
import { SettingsPage } from './views/SettingsPage';
import { CameraSettingsPage } from './views/CameraSettingsPage';


const INITIAL_CAMERAS: CameraStreamInfo[] = [
  {
    id: 'CAM_SEJONG_95366',
    name: '[세종]운학터널(세종)-13|13',
    sector: 'Sejong / Wunhak Tunnel',
    status: 'online',
    is_simulated: false,
    video_source: 'https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=95366',
    resolution: '720x480',
    fps: 30,
    active_alerts: 0,
  },
  {
    id: 'CAM_GITS_1809',
    name: '우체국4R(상행)',
    sector: 'Gwacheon / Post Office Intersection',
    status: 'online',
    is_simulated: false,
    video_source: 'https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=1809',
    resolution: '720x480',
    fps: 30,
    active_alerts: 0,
  },
  {
    id: 'CAM_01',
    name: 'Sector Alpha - North Perimeter Gate',
    sector: 'North Border Sector A',
    status: 'simulated',
    is_simulated: true,
    video_source: 'mock_streams/sample_patrol.mp4',
    resolution: '640x480',
    fps: 15,
    active_alerts: 0,
  },
  {
    id: 'CAM_02',
    name: 'Sector Alpha - South Vehicle Corridor',
    sector: 'South Transport Corridor',
    status: 'simulated',
    is_simulated: true,
    video_source: 'mock_streams/sample_patrol.mp4',
    resolution: '640x480',
    fps: 15,
    active_alerts: 0,
  },
  {
    id: 'CAM_03',
    name: 'Sector Bravo - East Virtual Fence',
    sector: 'Bravo East Exclusion Zone',
    status: 'simulated',
    is_simulated: true,
    video_source: 'mock_streams/sample_patrol.mp4',
    resolution: '640x480',
    fps: 15,
    active_alerts: 0,
  },
  {
    id: 'CAM_04',
    name: 'Sector Bravo - West Outpost',
    sector: 'Bravo West Boundary',
    status: 'simulated',
    is_simulated: true,
    video_source: 'mock_streams/sample_patrol.mp4',
    resolution: '640x480',
    fps: 15,
    active_alerts: 0,
  },
];

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>('dashboard');
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [cameras, setCameras] = useState<CameraStreamInfo[]>(INITIAL_CAMERAS);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [wsStatus, setWsStatus] = useState<WebSocketStatus>('disconnected');
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Synchronize REST data
  const syncData = useCallback(async () => {
    setIsRefreshing(true);
    setErrorBanner(null);
    try {
      const [alertsRes, healthRes, camerasRes] = await Promise.allSettled([
        fetchAlerts({ limit: 100 }),
        fetchHealth(),
        fetchCameras(),
      ]);

      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value.alerts);
      } else {
        console.debug('Alerts fetch failed (backend might be offline):', alertsRes.reason);
      }

      if (healthRes.status === 'fulfilled') {
        setHealth(healthRes.value);
      } else {
        setHealth(null);
      }

      if (camerasRes.status === 'fulfilled' && camerasRes.value.length > 0) {
        setCameras(camerasRes.value);
      }
    } catch (err: any) {
      setErrorBanner(err?.message || 'Failed to sync data with backend');
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Initial load and WebSocket subscription
  useEffect(() => {
    syncData();

    // Setup WebSocket listener
    const unsubscribeAlert = alertWsClient.onAlert((incomingAlert: Alert) => {
      setAlerts((prev) => {
        // Prevent duplicate alerts in state
        if (prev.some((a) => a.alert_id === incomingAlert.alert_id)) {
          return prev;
        }
        return [incomingAlert, ...prev];
      });
    });

    const unsubscribeStatus = alertWsClient.onStatusChange((status) => {
      setWsStatus(status);
    });

    alertWsClient.connect();

    return () => {
      unsubscribeAlert();
      unsubscribeStatus();
      alertWsClient.disconnect();
    };
  }, [syncData]);

  // Acknowledge Alert Handler
  const handleAcknowledge = async (alertId: string) => {
    setIsActionLoading(true);
    try {
      const updated = await acknowledgeAlert(alertId, 'operator_c2');
      setAlerts((prev) =>
        prev.map((a) => (a.alert_id === alertId ? updated : a))
      );
      if (selectedAlert?.alert_id === alertId) {
        setSelectedAlert(updated);
      }
    } catch (err: any) {
      alert(`Failed to acknowledge alert: ${err.message}`);
    } finally {
      setIsActionLoading(false);
    }
  };

  // Resolve Alert Handler
  const handleResolve = async (alertId: string, notes?: string) => {
    setIsActionLoading(true);
    try {
      const updated = await resolveAlert(alertId, 'operator_c2', notes);
      setAlerts((prev) =>
        prev.map((a) => (a.alert_id === alertId ? updated : a))
      );
      if (selectedAlert?.alert_id === alertId) {
        setSelectedAlert(updated);
      }
    } catch (err: any) {
      alert(`Failed to resolve alert: ${err.message}`);
    } finally {
      setIsActionLoading(false);
    }
  };

  const newAlertCount = alerts.filter((a) => a.status === 'new').length;
  const criticalCount = alerts.filter(
    (a) => a.severity === 'critical' && a.status !== 'resolved'
  ).length;

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#020617', color: '#f8fafc' }}>
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        newAlertCount={newAlertCount}
      />

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Header
          wsStatus={wsStatus}
          health={health}
          totalAlerts={alerts.length}
          criticalAlerts={criticalCount}
          cameras={cameras}
          onRefresh={syncData}
          isRefreshing={isRefreshing}
        />

        {errorBanner && (
          <div
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              borderBottom: '1px solid #ef4444',
              color: '#f87171',
              padding: '8px 1.5rem',
              fontSize: '0.8rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>{errorBanner}</span>
            <button
              onClick={() => setErrorBanner(null)}
              style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer' }}
            >
              ✕
            </button>
          </div>
        )}

        <main style={{ flex: 1, padding: '1.5rem', overflowY: 'auto' }}>
          {currentTab === 'dashboard' && (
            <DashboardHome
              alerts={alerts}
              cameras={cameras}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
              onInspect={setSelectedAlert}
              onSelectCamera={() => setCurrentTab('cameras')}
              isActionLoading={isActionLoading}
            />
          )}

          {currentTab === 'cameras' && (
            <CamerasPage
              cameras={cameras}
              alerts={alerts}
              onInspectAlert={setSelectedAlert}
            />
          )}

          {currentTab === 'alerts' && (
            <AlertsPage
              alerts={alerts}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
              onInspect={setSelectedAlert}
              isActionLoading={isActionLoading}
            />
          )}

          {currentTab === 'incidents' && <IncidentsPage />}

          {currentTab === 'events' && (
            <EventsPage alerts={alerts} onInspectAlert={setSelectedAlert} />
          )}


          {currentTab === 'camera-settings' && (
            <CameraSettingsPage cameras={cameras} onRefresh={syncData} />
          )}

          {currentTab === 'settings' && <SettingsPage health={health} />}
        </main>
      </div>

      {/* Alert Details Inspection Modal */}
      <AlertDetailModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
        isActionLoading={isActionLoading}
      />
    </div>
  );
};

export default App;
