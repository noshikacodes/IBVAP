import { WS_BASE_URL } from './config';
import { Alert, WebSocketStatus } from '../types';

export type AlertCallback = (alert: Alert) => void;
export type StatusCallback = (status: WebSocketStatus) => void;

export class AlertWebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private alertListeners: Set<AlertCallback> = new Set();
  private statusListeners: Set<StatusCallback> = new Set();
  private reconnectTimeout: number | null = null;
  private pingInterval: number | null = null;
  private retryDelay: number = 2000;
  private maxRetryDelay: number = 15000;
  private isIntentionallyClosed: boolean = false;
  public status: WebSocketStatus = 'disconnected';

  constructor(url: string = WS_BASE_URL) {
    this.url = url;
  }

  public connect(): void {
    this.isIntentionallyClosed = false;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.setStatus('connecting');

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.setStatus('connected');
        this.retryDelay = 2000; // Reset backoff
        this.startPing();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'NEW_ALERT' && message.data) {
            this.notifyAlert(message.data);
          }
        } catch (e) {
          console.debug('Failed to parse WebSocket message:', e);
        }
      };

      this.ws.onerror = () => {
        this.setStatus('error');
      };

      this.ws.onclose = () => {
        this.stopPing();
        this.setStatus('disconnected');
        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect();
        }
      };
    } catch (e) {
      this.setStatus('error');
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    this.stopPing();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  public onAlert(callback: AlertCallback): () => void {
    this.alertListeners.add(callback);
    return () => this.alertListeners.delete(callback);
  }

  public onStatusChange(callback: StatusCallback): () => void {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => this.statusListeners.delete(callback);
  }

  private setStatus(status: WebSocketStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.statusListeners.forEach((listener) => listener(status));
    }
  }

  private notifyAlert(alert: Alert): void {
    this.alertListeners.forEach((listener) => listener(alert));
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimeout || this.isIntentionallyClosed) return;

    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectTimeout = null;
      this.retryDelay = Math.min(this.retryDelay * 1.5, this.maxRetryDelay);
      this.connect();
    }, this.retryDelay);
  }

  private startPing(): void {
    this.stopPing();
    this.pingInterval = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ action: 'ping' }));
        } catch {
          // ignore
        }
      }
    }, 20000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

// Global default singleton
export const alertWsClient = new AlertWebSocketClient();
