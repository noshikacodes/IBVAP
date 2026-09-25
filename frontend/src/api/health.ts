import { API_BASE_URL } from './config';
import { HealthResponse } from '../types';

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed (status: ${response.status})`);
  }
  return response.json();
}
