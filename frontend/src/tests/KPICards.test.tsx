import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KPICards } from '../components/KPICards';

describe('KPICards Component', () => {
  it('renders all 4 surveillance metric cards with correct values', () => {
    render(
      <KPICards
        totalCameras={4}
        simulatedCameras={4}
        totalAlerts={15}
        newAlerts={6}
        criticalAlerts={2}
        uniqueViolatorsCount={8}
      />
    );

    expect(screen.getByText('SURVEILLANCE CAMERAS')).toBeDefined();
    expect(screen.getByText('4')).toBeDefined();
    expect(screen.getByText('15')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined();
    expect(screen.getByText('8')).toBeDefined();
    expect(screen.getByText(/4 Simulated \/ Demo Feeds/)).toBeDefined();
  });
});
