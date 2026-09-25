import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CameraSettingsPage } from '../views/CameraSettingsPage';
import { CameraStreamInfo } from '../types';
import * as cameraApi from '../api/cameras';

const MOCK_CAMERAS: CameraStreamInfo[] = [
  {
    id: 'CAM_01',
    name: 'Sector Alpha - North Perimeter Gate',
    sector: 'North Border Sector A',
    status: 'simulated',
    is_simulated: true,
    video_source: 'rtsp://localhost:8554/ibvap-cam01',
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
    video_source: 'rtsp://localhost:8554/ibvap-cam02',
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
    video_source: 'rtsp://localhost:8554/ibvap-cam03',
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
    video_source: 'rtsp://localhost:8554/ibvap-cam04',
    resolution: '640x480',
    fps: 15,
    active_alerts: 0,
  },
];

describe('CameraSettingsPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all 4 camera configuration cards with correct identifiers', () => {
    render(<CameraSettingsPage cameras={MOCK_CAMERAS} />);

    expect(screen.getByText('Camera & Stream Settings')).toBeDefined();
    expect(screen.getByText('CAM_01')).toBeDefined();
    expect(screen.getByText('CAM_02')).toBeDefined();
    expect(screen.getByText('CAM_03')).toBeDefined();
    expect(screen.getByText('CAM_04')).toBeDefined();

    // Verify badges
    const simulatedBadges = screen.getAllByText('SIMULATED / DEMO');
    expect(simulatedBadges.length).toBeGreaterThanOrEqual(4);
  });

  it('allows switching between SIMULATED / DEMO and RTSP / IP CAMERA modes', async () => {
    render(<CameraSettingsPage cameras={MOCK_CAMERAS} />);

    const rtspButtons = screen.getAllByText('RTSP / IP CAMERA');
    expect(rtspButtons.length).toBe(4);

    // Click RTSP button for CAM_01
    fireEvent.click(rtspButtons[0]);

    // Check that Username & Password fields appear for CAM_01
    expect(screen.getByPlaceholderText('admin')).toBeDefined();
    expect(screen.getByPlaceholderText('••••••••')).toBeDefined();
  });

  it('handles connection test and renders diagnostics HUD panel', async () => {
    const mockTestResult = {
      camera_id: 'CAM_01',
      reachable: true,
      status: 'online',
      protocol: 'RTSP',
      codec: 'h264',
      resolution: '1280x720',
      fps: 30,
      latency_ms: 124.5,
      relay_status: 'ACTIVE',
      hls_status: 'READY',
      masked_url: 'rtsp://***:***@192.168.1.50:554/live',
      error_reason: undefined,
    };

    const testSpy = vi.spyOn(cameraApi, 'testCameraConnection').mockResolvedValue(mockTestResult);

    render(<CameraSettingsPage cameras={MOCK_CAMERAS} />);

    // Click Test Connection for CAM_01
    const testButtons = screen.getAllByText('TEST CONNECTION');
    fireEvent.click(testButtons[0]);

    await waitFor(() => {
      expect(testSpy).toHaveBeenCalledWith('CAM_01', expect.anything());
      expect(screen.getByText('1280x720')).toBeDefined();
      expect(screen.getByText('124.5 ms')).toBeDefined();
      expect(screen.getByText('ONLINE')).toBeDefined();
    });
  });

  it('saves camera configuration and calls updateCameraSource API', async () => {
    const updateSpy = vi.spyOn(cameraApi, 'updateCameraSource').mockResolvedValue({
      id: 'CAM_01',
      name: 'North Perimeter Gate IP Cam',
      sector: 'Sector Alpha',
      status: 'online',
      is_simulated: false,
      video_source: 'rtsp://192.168.1.101:8554/live',
      resolution: '1280x720',
      fps: 30,
      active_alerts: 0,
    });

    render(<CameraSettingsPage cameras={MOCK_CAMERAS} />);

    const saveButtons = screen.getAllByText('SAVE CONFIGURATION');
    fireEvent.click(saveButtons[0]);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith('CAM_01', expect.anything());
    });
  });

  it('resets camera to simulated demo stream', async () => {
    const resetSpy = vi.spyOn(cameraApi, 'resetCameraDemo').mockResolvedValue({
      id: 'CAM_01',
      name: 'Sector Alpha - North Perimeter Gate',
      sector: 'North Border Sector A',
      status: 'simulated',
      is_simulated: true,
      video_source: 'rtsp://localhost:8554/ibvap-cam01',
      resolution: '640x480',
      fps: 15,
      active_alerts: 0,
    });

    render(<CameraSettingsPage cameras={MOCK_CAMERAS} />);

    const resetButtons = screen.getAllByText('RESET TO DEMO');
    fireEvent.click(resetButtons[0]);

    await waitFor(() => {
      expect(resetSpy).toHaveBeenCalledWith('CAM_01');
      expect(screen.getByText('Reset slot to default synthetic demo stream.')).toBeDefined();
    });
  });
});
