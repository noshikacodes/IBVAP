/// <reference types="vite/client" />

export const API_BASE_URL =
  ((import.meta as any).env?.VITE_API_BASE_URL as string) || 'http://localhost:8000/api/v1';

export const WS_BASE_URL =
  ((import.meta as any).env?.VITE_WS_BASE_URL as string) || 'ws://localhost:8000/api/v1/ws/alerts';
