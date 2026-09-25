import React, { useState, useEffect } from 'react';
import {
  Activity,
  Car,
  Truck,
  Bus,
  User,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  ShieldCheck,
  Zap,
  BarChart2,
} from 'lucide-react';

interface TrafficAnalyticsData {
  camera_id: string;
  today_totals: {
    car: number;
    bus: number;
    truck: number;
    motorcycle: number;
    person: number;
  };
  total_today: number;
  total_vehicles_today: number;
  total_persons_today: number;
  last_hour: number;
  last_10_minutes: number;
  total_all_time: number;
  live_now: {
    car: number;
    bus: number;
    truck: number;
    motorcycle: number;
    person: number;
  };
  live_total: number;
  counting_line: number[][];
  fps: number;
  frame_idx: number;
  active_tracks: number;
  status: string;
  timestamp: string;
}

interface TrafficEvent {
  id: number;
  camera_id: string;
  track_id: number;
  object_type: string;
  timestamp: string;
  direction: string;
  event_type: string;
  confidence: number;
  bbox_x1?: number;
  bbox_y1?: number;
  bbox_x2?: number;
  bbox_y2?: number;
}

interface TimeSeriesInterval {
  time_bucket: string;
  time_label: string;
  vehicles: number;
  breakdown: Record<string, number>;
}

interface TrafficAnalyticsPanelProps {
  cameraId: string;
  cameraName?: string;
}

export const TrafficAnalyticsPanel: React.FC<TrafficAnalyticsPanelProps> = ({
  cameraId,
  cameraName,
}) => {
  const [analytics, setAnalytics] = useState<TrafficAnalyticsData | null>(null);
  const [events, setEvents] = useState<TrafficEvent[]>([]);
  const [intervals, setIntervals] = useState<TimeSeriesInterval[]>([]);
  const [lastSync, setLastSync] = useState<string>('Just now');
  const [newestEventId, setNewestEventId] = useState<number | null>(null);

  // Poll analytics data
  useEffect(() => {
    let isMounted = true;

    const fetchAnalytics = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/v1/cameras/${cameraId}/traffic-analytics`);
        if (res.ok && isMounted) {
          const data: TrafficAnalyticsData = await res.json();
          setAnalytics(data);
          setLastSync(new Date().toLocaleTimeString());
        }
      } catch (err) {
        // Silently continue polling
      }
    };

    const fetchEvents = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/v1/cameras/${cameraId}/traffic-events?limit=25`);
        if (res.ok && isMounted) {
          const data = await res.json();
          const evts: TrafficEvent[] = data.events || [];
          if (evts.length > 0 && evts[0].id !== newestEventId) {
            setNewestEventId(evts[0].id);
          }
          setEvents(evts);
        }
      } catch (err) {
        // Silently continue polling
      }
    };

    const fetchSummary = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/v1/cameras/${cameraId}/traffic-summary?limit=8`);
        if (res.ok && isMounted) {
          const data = await res.json();
          setIntervals(data.intervals || []);
        }
      } catch (err) {
        // Silently continue polling
      }
    };

    fetchAnalytics();
    fetchEvents();
    fetchSummary();

    const analyticsInterval = setInterval(fetchAnalytics, 750);
    const eventsInterval = setInterval(fetchEvents, 1500);
    const summaryInterval = setInterval(fetchSummary, 4000);

    return () => {
      isMounted = false;
      clearInterval(analyticsInterval);
      clearInterval(eventsInterval);
      clearInterval(summaryInterval);
    };
  }, [cameraId, newestEventId]);

  const liveNow = analytics?.live_now || { car: 0, bus: 0, truck: 0, motorcycle: 0, person: 0 };
  const todayTotals = analytics?.today_totals || { car: 0, bus: 0, truck: 0, motorcycle: 0, person: 0 };

  const getClassIcon = (cls: string) => {
    switch (cls.toLowerCase()) {
      case 'bus':
        return <Bus size={14} className="text-purple-400" />;
      case 'truck':
        return <Truck size={14} className="text-amber-400" />;
      case 'motorcycle':
        return <Zap size={14} className="text-cyan-400" />;
      case 'person':
        return <User size={14} className="text-emerald-400" />;
      default:
        return <Car size={14} className="text-sky-400" />;
    }
  };

  const getClassBadgeColor = (cls: string) => {
    switch (cls.toLowerCase()) {
      case 'bus':
        return { bg: 'rgba(168, 85, 247, 0.15)', text: '#c084fc', border: 'rgba(168, 85, 247, 0.4)' };
      case 'truck':
        return { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.4)' };
      case 'motorcycle':
        return { bg: 'rgba(6, 182, 212, 0.15)', text: '#22d3ee', border: 'rgba(6, 182, 212, 0.4)' };
      case 'person':
        return { bg: 'rgba(34, 197, 94, 0.15)', text: '#4ade80', border: 'rgba(34, 197, 94, 0.4)' };
      default:
        return { bg: 'rgba(56, 189, 248, 0.15)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.4)' };
    }
  };

  // Max vehicles in time-series intervals for chart scaling
  const maxVehicles = Math.max(...intervals.map((i) => i.vehicles), 5);

  return (
    <div
      style={{
        backgroundColor: '#0b1120',
        borderRadius: '8px',
        border: '1px solid #1e293b',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
        padding: '1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
        color: '#e2e8f0',
        fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* 1. Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #1e293b',
          paddingBottom: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={18} style={{ color: '#38bdf8' }} />
          <div>
            <div style={{ fontSize: '0.88rem', fontWeight: 800, letterSpacing: '0.05em', color: '#f8fafc' }}>
              TRAFFIC INTELLIGENCE // C2
            </div>
            <div style={{ fontSize: '0.65rem', color: '#64748b' }}>
              {cameraName || cameraId} • UNIQUE VEHICLE MOT ENGINE
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              backgroundColor: 'rgba(34, 197, 94, 0.15)',
              color: '#4ade80',
              border: '1px solid rgba(34, 197, 94, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.65rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
            LIVE MOT ACTIVE
          </span>
          <span style={{ fontSize: '0.65rem', color: '#64748b', fontFamily: 'monospace' }}>
            {lastSync}
          </span>
        </div>
      </div>

      {/* 2. LIVE NOW Matrix */}
      <div>
        <div
          style={{
            fontSize: '0.72rem',
            fontWeight: 800,
            letterSpacing: '0.08em',
            color: '#38bdf8',
            marginBottom: '0.6rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <Zap size={14} />
          LIVE NOW (CURRENTLY IN VIEW)
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '6px' }}>
          {[
            { key: 'car', label: 'Cars', count: liveNow.car, color: '#38bdf8' },
            { key: 'bus', label: 'Buses', count: liveNow.bus, color: '#c084fc' },
            { key: 'truck', label: 'Trucks', count: liveNow.truck, color: '#fbbf24' },
            { key: 'motorcycle', label: 'M-Cycles', count: liveNow.motorcycle, color: '#22d3ee' },
            { key: 'person', label: 'Persons', count: liveNow.person, color: '#4ade80' },
          ].map((item) => (
            <div
              key={item.key}
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '6px',
                padding: '8px 6px',
                textAlign: 'center',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ fontSize: '0.62rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>
                {item.label}
              </div>
              <div
                style={{
                  fontSize: '1.25rem',
                  fontWeight: 900,
                  fontFamily: 'monospace',
                  color: item.count > 0 ? item.color : '#475569',
                  marginTop: '2px',
                }}
              >
                {item.count}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. TODAY CUMULATIVE COUNTERS */}
      <div
        style={{
          backgroundColor: '#090d16',
          borderRadius: '8px',
          border: '1px solid #1e293b',
          padding: '1rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '0.75rem',
          }}
        >
          <div
            style={{
              fontSize: '0.72rem',
              fontWeight: 800,
              letterSpacing: '0.08em',
              color: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <ShieldCheck size={14} style={{ color: '#22c55e' }} />
            TODAY CUMULATIVE (UNIQUE COUNT)
          </div>
          <span
            style={{
              fontSize: '0.62rem',
              color: '#64748b',
              backgroundColor: '#0f172a',
              padding: '2px 6px',
              borderRadius: '4px',
              border: '1px solid #1e293b',
            }}
          >
            STRICT 1x PER VEHICLE
          </span>
        </div>

        {/* Big Total Counter */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '0.75rem' }}>
          <div
            style={{
              backgroundColor: 'rgba(56, 189, 248, 0.08)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '6px',
              padding: '8px 10px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '0.62rem', color: '#38bdf8', fontWeight: 700 }}>TOTAL VEHICLES TODAY</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, fontFamily: 'monospace', color: '#f8fafc' }}>
              {analytics?.total_vehicles_today ?? 0}
            </div>
          </div>
          <div
            style={{
              backgroundColor: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '8px 10px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '0.62rem', color: '#94a3b8', fontWeight: 600 }}>PAST 1 HOUR</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, fontFamily: 'monospace', color: '#e2e8f0' }}>
              {analytics?.last_hour ?? 0}
            </div>
          </div>
          <div
            style={{
              backgroundColor: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '8px 10px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '0.62rem', color: '#94a3b8', fontWeight: 600 }}>PAST 10 MIN</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, fontFamily: 'monospace', color: '#4ade80' }}>
              {analytics?.last_10_minutes ?? 0}
            </div>
          </div>
        </div>

        {/* Detailed Breakdown List */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '6px' }}>
          {[
            { label: 'Cars', count: todayTotals.car, color: '#38bdf8', icon: <Car size={12} /> },
            { label: 'Buses', count: todayTotals.bus, color: '#c084fc', icon: <Bus size={12} /> },
            { label: 'Trucks', count: todayTotals.truck, color: '#fbbf24', icon: <Truck size={12} /> },
            { label: 'M-Cycles', count: todayTotals.motorcycle, color: '#22d3ee', icon: <Zap size={12} /> },
            { label: 'Persons', count: todayTotals.person, color: '#4ade80', icon: <User size={12} /> },
          ].map((c) => (
            <div
              key={c.label}
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '5px',
                padding: '6px 4px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '3px', color: c.color }}>
                {c.icon}
                <span style={{ fontSize: '0.62rem', fontWeight: 600 }}>{c.label}</span>
              </div>
              <span style={{ fontSize: '1rem', fontWeight: 800, fontFamily: 'monospace', color: '#f8fafc', marginTop: '2px' }}>
                {c.count}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 4. HISTORICAL TRAFFIC VOLUME TIME-SERIES CHART */}
      <div
        style={{
          backgroundColor: '#090d16',
          borderRadius: '8px',
          border: '1px solid #1e293b',
          padding: '1rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '0.75rem',
          }}
        >
          <div
            style={{
              fontSize: '0.72rem',
              fontWeight: 800,
              letterSpacing: '0.08em',
              color: '#38bdf8',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <BarChart2 size={14} />
            TRAFFIC VOLUME TIME-SERIES (INTERVALS)
          </div>
          <span style={{ fontSize: '0.62rem', color: '#64748b' }}>ROLLING INTERVALS</span>
        </div>

        {intervals.length === 0 ? (
          <div
            style={{
              height: '70px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#64748b',
              fontSize: '0.72rem',
              fontStyle: 'italic',
            }}
          >
            Awaiting rolling interval aggregation...
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'flex-end', height: '80px', gap: '8px', padding: '0 4px' }}>
            {intervals.map((item, idx) => {
              const heightPct = Math.max(10, Math.min(100, Math.round((item.vehicles / maxVehicles) * 100)));
              return (
                <div
                  key={item.time_bucket || idx}
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '4px',
                    height: '100%',
                    justifyContent: 'flex-end',
                  }}
                  title={`${item.time_label}: ${item.vehicles} vehicles`}
                >
                  <div style={{ fontSize: '0.62rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                    {item.vehicles}
                  </div>
                  <div
                    style={{
                      width: '100%',
                      height: `${heightPct}%`,
                      backgroundColor: '#38bdf8',
                      backgroundImage: 'linear-gradient(to top, rgba(56, 189, 248, 0.4), rgba(56, 189, 248, 0.9))',
                      borderRadius: '3px 3px 0 0',
                      transition: 'height 0.4s ease-out',
                    }}
                  />
                  <div style={{ fontSize: '0.58rem', color: '#64748b', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                    {item.time_label}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 5. LIVE TRAFFIC EVENT FEED */}
      <div
        style={{
          backgroundColor: '#090d16',
          borderRadius: '8px',
          border: '1px solid #1e293b',
          padding: '1rem',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '260px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '0.6rem',
          }}
        >
          <div
            style={{
              fontSize: '0.72rem',
              fontWeight: 800,
              letterSpacing: '0.08em',
              color: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Clock size={14} style={{ color: '#38bdf8' }} />
            LIVE TRAFFIC CROSSING FEED
          </div>
          <span style={{ fontSize: '0.62rem', color: '#22c55e', fontFamily: 'monospace' }}>
            ● STREAMING
          </span>
        </div>

        {events.length === 0 ? (
          <div
            style={{
              padding: '1.5rem',
              textAlign: 'center',
              color: '#64748b',
              fontSize: '0.72rem',
              fontStyle: 'italic',
            }}
          >
            Monitoring roadway... Crossing events will appear here in real-time as vehicles cross the virtual line.
          </div>
        ) : (
          <div
            style={{
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '5px',
              paddingRight: '4px',
            }}
          >
            {events.map((evt, idx) => {
              const badge = getClassBadgeColor(evt.object_type);
              const timeStr = evt.timestamp.includes('T')
                ? evt.timestamp.split('T')[1].slice(0, 8)
                : evt.timestamp.slice(11, 19);

              return (
                <div
                  key={evt.id || idx}
                  style={{
                    backgroundColor: evt.id === newestEventId ? 'rgba(56, 189, 248, 0.12)' : '#0f172a',
                    border: `1px solid ${evt.id === newestEventId ? 'rgba(56, 189, 248, 0.4)' : '#1e293b'}`,
                    borderRadius: '4px',
                    padding: '6px 8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.72rem',
                    transition: 'all 0.3s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontFamily: 'monospace', color: '#64748b', fontSize: '0.68rem' }}>
                      {timeStr}
                    </span>
                    <span
                      style={{
                        backgroundColor: badge.bg,
                        color: badge.text,
                        border: `1px solid ${badge.border}`,
                        padding: '1px 6px',
                        borderRadius: '3px',
                        fontWeight: 700,
                        fontSize: '0.62rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        textTransform: 'uppercase',
                      }}
                    >
                      {getClassIcon(evt.object_type)}
                      {evt.object_type}
                    </span>
                    <span style={{ fontFamily: 'monospace', color: '#94a3b8', fontSize: '0.68rem' }}>
                      Track #{evt.track_id}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        color: evt.direction === 'IN' ? '#38bdf8' : '#34d399',
                        fontWeight: 700,
                        fontSize: '0.65rem',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      {evt.direction === 'IN' ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                      {evt.direction}
                    </span>
                    <span
                      style={{
                        backgroundColor: 'rgba(34, 197, 94, 0.2)',
                        color: '#4ade80',
                        border: '1px solid rgba(34, 197, 94, 0.4)',
                        padding: '1px 5px',
                        borderRadius: '3px',
                        fontFamily: 'monospace',
                        fontWeight: 800,
                        fontSize: '0.62rem',
                      }}
                    >
                      +1
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
