import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { IncidentsPage } from '../views/IncidentsPage';

describe('IncidentsPage Component', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('/api/v1/incidents')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            total: 1,
            incidents: [
              {
                incident_id: 'INC-2026-0041',
                title: 'Perimeter Fence Intrusion & PTZ Lock',
                severity: 'critical',
                status: 'open',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                sector: 'Bravo East Exclusion Zone',
                primary_camera_id: 'CAM_FENCE',
                track_ids: [104],
                description: 'Autonomous spatial rule breach detected.',
                summary: 'Suspect detected at perimeter fence.',
                evidence_items: [
                  {
                    evidence_id: 'ev_8a91b2c3',
                    evidence_type: 'zone_breach',
                    timestamp: new Date().toISOString(),
                    camera_id: 'CAM_FENCE',
                    sha256_hash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
                    data: { track_id: 104, zone: 'ZONE_NORTH_PERIMETER' },
                  }
                ],
                timeline: [
                  {
                    entry_id: 'tl_001',
                    timestamp: new Date().toISOString(),
                    source: 'AI_SPATIAL_RULES',
                    severity: 'critical',
                    event_type: 'virtual_fence_breach',
                    description: 'Intruder crossed perimeter fence',
                    camera_id: 'CAM_FENCE',
                    details: {},
                  }
                ],
                dispatches: [],
                dossier_hash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
                metadata: {},
              }
            ]
          })
        });
      }
      return Promise.reject(new Error('Unknown url'));
    }));
  });

  it('renders tactical incidents header and loads incident dossier', async () => {
    render(<IncidentsPage />);

    expect(screen.getByText(/Tactical Incident Dossiers & Multi-Agency Dispatch/i)).toBeDefined();
    
    await waitFor(() => {
      expect(screen.getAllByText('INC-2026-0041').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Perimeter Fence Intrusion & PTZ Lock').length).toBeGreaterThan(0);
      expect(screen.getByText(/Export PDF/i)).toBeDefined();
      expect(screen.getByText(/JSON Dossier/i)).toBeDefined();
      expect(screen.getByText(/DISPATCH TACTICAL ALERT/i)).toBeDefined();
    });
  });
});

