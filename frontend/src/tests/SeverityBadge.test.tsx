import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge } from '../components/SeverityBadge';

describe('SeverityBadge Component', () => {
  it('renders critical severity label correctly', () => {
    render(<SeverityBadge severity="critical" />);
    expect(screen.getByText('CRITICAL')).toBeDefined();
  });

  it('renders high severity label correctly', () => {
    render(<SeverityBadge severity="high" />);
    expect(screen.getByText('HIGH')).toBeDefined();
  });

  it('renders medium severity label correctly', () => {
    render(<SeverityBadge severity="medium" />);
    expect(screen.getByText('MEDIUM')).toBeDefined();
  });

  it('renders low severity label correctly', () => {
    render(<SeverityBadge severity="low" />);
    expect(screen.getByText('LOW')).toBeDefined();
  });
});
