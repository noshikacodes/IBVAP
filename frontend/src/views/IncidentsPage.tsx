import React, { useState, useEffect } from 'react';
import { Incident, IncidentStatus } from '../types';
import { SeverityBadge } from '../components/SeverityBadge';
import {
  FileText,
  Send,
  Download,
  Clock,
  Lock,
  Layers,
  RefreshCw,
} from 'lucide-react';


interface IncidentsPageProps {
  initialIncidentId?: string | null;
}

export const IncidentsPage: React.FC<IncidentsPageProps> = ({ initialIncidentId }) => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(initialIncidentId || null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [dispatching, setDispatching] = useState<boolean>(false);
  const [selectedAgencies, setSelectedAgencies] = useState<string[]>([
    'quick_reaction_team_qrt',
    'border_patrol_command',
  ]);
  const [dispatchNotes, setDispatchNotes] = useState<string>('Perimeter security intrusion breach - urgent dispatch');

  const fetchIncidents = async () => {
    try {
      setLoading(true);
      const res = await fetch('http://localhost:8000/api/v1/incidents');
      if (res.ok) {
        const data = await res.json();
        setIncidents(data.incidents || []);
        if (!selectedIncidentId && data.incidents.length > 0) {
          setSelectedIncidentId(data.incidents[0].incident_id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch incidents', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  const selectedIncident = incidents.find((i) => i.incident_id === selectedIncidentId) || incidents[0];

  const handleAgencyToggle = (agency: string) => {
    if (selectedAgencies.includes(agency)) {
      setSelectedAgencies(selectedAgencies.filter((a) => a !== agency));
    } else {
      setSelectedAgencies([...selectedAgencies, agency]);
    }
  };

  const handleExecuteDispatch = async () => {
    if (!selectedIncident || selectedAgencies.length === 0) return;
    setDispatching(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/incidents/${selectedIncident.incident_id}/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agencies: selectedAgencies,
          notes: dispatchNotes,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setIncidents((prev) =>
          prev.map((inc) => (inc.incident_id === updated.incident_id ? updated : inc))
        );
      }
    } catch (err) {
      console.error('Dispatch execution failed', err);
    } finally {
      setDispatching(false);
    }
  };

  const handleDownloadDossier = (type: 'json' | 'pdf') => {
    if (!selectedIncident) return;
    const url = `http://localhost:8000/api/v1/incidents/${selectedIncident.incident_id}/dossier/${type}`;
    window.open(url, '_blank');
  };

  const filteredIncidents = incidents.filter((i) => {
    if (filterStatus === 'all') return true;
    return i.status === filterStatus;
  });

  const renderStatusBadge = (status: IncidentStatus) => {
    switch (status) {
      case 'open':
        return (
          <span style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700 }}>
            OPEN
          </span>
        );
      case 'dispatched':
        return (
          <span style={{ backgroundColor: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.4)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700 }}>
            DISPATCHED
          </span>
        );
      case 'in_investigation':
        return (
          <span style={{ backgroundColor: 'rgba(234, 179, 8, 0.15)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.4)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700 }}>
            INVESTIGATING
          </span>
        );
      case 'resolved':
      case 'closed':
        return (
          <span style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.4)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700 }}>
            RESOLVED
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Page Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #1e293b',
          paddingBottom: '1rem',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 4px 0', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={22} color="#38bdf8" />
            Tactical Incident Dossiers & Multi-Agency Dispatch
          </h2>
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
            Cryptographically sealed incident dossiers, multi-sensor timeline reconstruction, and authenticated inter-agency dispatch
          </p>
        </div>

        <button
          onClick={fetchIncidents}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '6px',
            padding: '6px 12px',
            color: '#f8fafc',
            cursor: 'pointer',
            fontSize: '0.78rem',
            fontWeight: 600,
          }}
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh Ledger
        </button>
      </div>

      {/* Main 2-Column Split View */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 1.1fr) minmax(550px, 2fr)', gap: '1.25rem', alignItems: 'start' }}>
        {/* Left Column: Incidents Filter & List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {/* Status Filter Buttons */}
          <div style={{ display: 'flex', gap: '6px', backgroundColor: '#0f172a', padding: '6px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            {['all', 'open', 'dispatched', 'resolved'].map((st) => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                style={{
                  flex: 1,
                  padding: '5px 8px',
                  borderRadius: '5px',
                  border: 'none',
                  backgroundColor: filterStatus === st ? '#38bdf8' : 'transparent',
                  color: filterStatus === st ? '#0f172a' : '#94a3b8',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  textTransform: 'uppercase',
                }}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Incident Cards List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '720px', overflowY: 'auto' }}>
            {filteredIncidents.length === 0 ? (
              <div style={{ backgroundColor: '#0f172a', padding: '2rem', borderRadius: '8px', border: '1px solid #1e293b', textAlign: 'center', color: '#64748b', fontSize: '0.8rem' }}>
                No incidents match filter
              </div>
            ) : (
              filteredIncidents.map((inc) => {
                const isSelected = selectedIncident?.incident_id === inc.incident_id;
                return (
                  <div
                    key={inc.incident_id}
                    onClick={() => setSelectedIncidentId(inc.incident_id)}
                    style={{
                      backgroundColor: isSelected ? '#1e293b' : '#0f172a',
                      border: isSelected ? '1px solid #38bdf8' : '1px solid #1e293b',
                      borderRadius: '8px',
                      padding: '0.85rem 1rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'monospace' }}>
                        {inc.incident_id}
                      </span>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <SeverityBadge severity={inc.severity} size="sm" />
                        {renderStatusBadge(inc.status)}
                      </div>
                    </div>

                    <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#f8fafc', marginBottom: '4px' }}>
                      {inc.title}
                    </div>

                    <div style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'flex', justifyContent: 'space-between' }}>
                      <span>{inc.sector}</span>
                      <span>{inc.evidence_items.length} Evidence • {inc.dispatches.length} Dispatches</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Selected Incident Detailed Dossier */}
        {selectedIncident && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Incident Header & Dossier Actions Card */}
            <div
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #1e293b', paddingBottom: '1rem', marginBottom: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'monospace' }}>
                      {selectedIncident.incident_id}
                    </span>
                    <SeverityBadge severity={selectedIncident.severity} size="md" />
                    {renderStatusBadge(selectedIncident.status)}
                  </div>
                  <h3 style={{ margin: '0 0 6px 0', fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc' }}>
                    {selectedIncident.title}
                  </h3>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                    Sector: <strong>{selectedIncident.sector}</strong> • Primary Sensor: <strong>{selectedIncident.primary_camera_id}</strong> • Declared: {new Date(selectedIncident.created_at).toLocaleString()}
                  </div>
                </div>

                {/* Dossier Download Actions */}
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => handleDownloadDossier('pdf')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      backgroundColor: 'rgba(56, 189, 248, 0.15)',
                      border: '1px solid rgba(56, 189, 248, 0.4)',
                      borderRadius: '6px',
                      padding: '6px 12px',
                      color: '#38bdf8',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                    }}
                  >
                    <Download size={14} /> Export PDF
                  </button>
                  <button
                    onClick={() => handleDownloadDossier('json')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '6px',
                      padding: '6px 12px',
                      color: '#f8fafc',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                    }}
                  >
                    <Download size={14} /> JSON Dossier
                  </button>
                </div>
              </div>

              {/* Cryptographic SHA-256 Seal Banner */}
              <div
                style={{
                  backgroundColor: '#090d16',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '0.72rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#4ade80', fontWeight: 600 }}>
                  <Lock size={14} />
                  <span>IMMUTABLE EVIDENCE LEDGER SEALED</span>
                </div>
                <div style={{ color: '#64748b', fontFamily: 'monospace' }}>
                  SHA256: {selectedIncident.dossier_hash || 'CALCULATED_ON_EXPORT'}
                </div>
              </div>
            </div>

            {/* Multi-Agency Dispatch Action Panel */}
            <div
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem' }}>
                <Send size={16} color="#38bdf8" />
                <span style={{ fontWeight: 800, fontSize: '0.92rem', color: '#f8fafc' }}>
                  Multi-Agency Tactical Alert Dispatch Console
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                {[
                  { id: 'quick_reaction_team_qrt', name: 'Quick Reaction Team (QRT)' },
                  { id: 'border_patrol_command', name: 'Border Patrol Sector HQ' },
                  { id: 'customs_intelligence', name: 'Customs Intelligence' },
                  { id: 'local_law_enforcement', name: 'District Police Interdiction' },
                ].map((ag) => {
                  const isChecked = selectedAgencies.includes(ag.id);
                  return (
                    <label
                      key={ag.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        backgroundColor: isChecked ? 'rgba(56, 189, 248, 0.12)' : '#090d16',
                        border: isChecked ? '1px solid #38bdf8' : '1px solid #1e293b',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '0.75rem',
                        color: isChecked ? '#f8fafc' : '#94a3b8',
                        fontWeight: 600,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleAgencyToggle(ag.id)}
                      />
                      <span>{ag.name}</span>
                    </label>
                  );
                })}
              </div>

              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="text"
                  value={dispatchNotes}
                  onChange={(e) => setDispatchNotes(e.target.value)}
                  placeholder="Operator notes for dispatched tactical units..."
                  style={{
                    flex: 1,
                    backgroundColor: '#090d16',
                    border: '1px solid #334155',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#f8fafc',
                    fontSize: '0.78rem',
                  }}
                />
                <button
                  onClick={handleExecuteDispatch}
                  disabled={dispatching || selectedAgencies.length === 0}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor: '#38bdf8',
                    color: '#0f172a',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '8px 16px',
                    fontWeight: 800,
                    fontSize: '0.78rem',
                    cursor: dispatching ? 'not-allowed' : 'pointer',
                  }}
                >
                  <Send size={14} />
                  {dispatching ? 'DISPATCHING...' : 'DISPATCH TACTICAL ALERT'}
                </button>
              </div>

              {/* Active Dispatch Acknowledgements Log */}
              {selectedIncident.dispatches.length > 0 && (
                <div style={{ marginTop: '1rem', borderTop: '1px solid #1e293b', paddingTop: '0.75rem' }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', marginBottom: '6px' }}>
                    RECENT DISPATCH CONFIRMATIONS ({selectedIncident.dispatches.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {selectedIncident.dispatches.map((disp) => (
                      <div
                        key={disp.dispatch_id}
                        style={{
                          backgroundColor: '#090d16',
                          border: '1px solid #1e293b',
                          borderRadius: '6px',
                          padding: '6px 10px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '0.72rem',
                        }}
                      >
                        <div>
                          <strong style={{ color: '#f8fafc' }}>{disp.agency_name}</strong>
                          <span style={{ color: '#64748b', marginLeft: '6px' }}>
                            Ref: {disp.ack_reference || 'DELIVERED'}
                          </span>
                        </div>
                        <span style={{ color: '#4ade80', fontWeight: 700 }}>
                          ✓ {disp.status.toUpperCase()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Chronological Sensor Fusion Timeline */}
            <div
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem' }}>
                <Clock size={16} color="#38bdf8" />
                <span style={{ fontWeight: 800, fontSize: '0.92rem', color: '#f8fafc' }}>
                  Chronological Sensor Fusion Timeline ({selectedIncident.timeline.length} Events)
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', position: 'relative', paddingLeft: '1rem', borderLeft: '2px solid #334155' }}>
                {selectedIncident.timeline.map((entry) => (
                  <div key={entry.entry_id} style={{ position: 'relative' }}>
                    <div
                      style={{
                        position: 'absolute',
                        left: '-1.45rem',
                        top: '4px',
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: '#38bdf8',
                      }}
                    />
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                      <span style={{ color: '#64748b', fontSize: '0.68rem', fontFamily: 'monospace' }}>
                        {new Date(entry.timestamp).toLocaleTimeString([], { hour12: false })}
                      </span>
                      <span style={{ backgroundColor: '#1e293b', color: '#38bdf8', padding: '1px 6px', borderRadius: '3px', fontSize: '0.65rem', fontWeight: 700 }}>
                        {entry.source}
                      </span>
                    </div>
                    <div style={{ color: '#f8fafc', fontSize: '0.78rem', fontWeight: 600 }}>
                      {entry.description}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Immutable Evidence Ledger */}
            <div
              style={{
                backgroundColor: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem' }}>
                <Layers size={16} color="#38bdf8" />
                <span style={{ fontWeight: 800, fontSize: '0.92rem', color: '#f8fafc' }}>
                  Itemized Evidence Ledger ({selectedIncident.evidence_items.length} Artifacts)
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem' }}>
                {selectedIncident.evidence_items.map((ev) => (
                  <div
                    key={ev.evidence_id}
                    style={{
                      backgroundColor: '#090d16',
                      border: '1px solid #1e293b',
                      borderRadius: '6px',
                      padding: '10px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ backgroundColor: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', padding: '2px 6px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700 }}>
                        {ev.evidence_type.toUpperCase()}
                      </span>
                      <span style={{ color: '#64748b', fontSize: '0.68rem' }}>{ev.camera_id}</span>
                    </div>
                    <div style={{ color: '#94a3b8', fontSize: '0.7rem', fontFamily: 'monospace', margin: '4px 0' }}>
                      SHA256: {ev.sha256_hash.slice(0, 16)}...
                    </div>
                    <pre style={{ margin: 0, color: '#e2e8f0', fontSize: '0.65rem', backgroundColor: '#020617', padding: '6px', borderRadius: '4px', overflowX: 'auto' }}>
                      {JSON.stringify(ev.data, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
