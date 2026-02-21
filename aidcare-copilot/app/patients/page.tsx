'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Icon from '../../components/Icon';
import { getPatients, getPatientDetail, getPatientAISummary, getError } from '../../lib/api';
import { getSessionUser } from '../../lib/session';
import { Patient, PatientDetail, Consultation } from '../../types';

interface AISummary {
  chronic_conditions: { condition: string; details: string }[];
  flagged_patterns: string[];
  summary: string;
}

export default function PatientsPage() {
  const router = useRouter();
  const user = typeof window !== 'undefined' ? getSessionUser() : null;
  const [groups, setGroups] = useState<{ critical: Patient[]; stable: Patient[]; discharged: Patient[] }>({ critical: [], stable: [], discharged: [] });
  const [detail, setDetail] = useState<PatientDetail | null>(null);
  const [aiSummary, setAiSummary] = useState<AISummary | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [soapSearch, setSoapSearch] = useState('');

  useEffect(() => {
    if (!user) { router.push('/login'); return; }
    loadAll();
  }, []);

  async function loadAll() {
    try {
      const d = await getPatients();
      setGroups(d.patients);
      const all = [...d.patients.critical, ...d.patients.stable, ...d.patients.discharged];
      if (all.length > 0) selectPatient(all[0].patient_id);
    } catch {} finally { setLoading(false); }
  }

  async function selectPatient(id: string) {
    try {
      const d = await getPatientDetail(id);
      setDetail(d);
      setAiSummary(null);
      setAiLoading(true);
      getPatientAISummary(id).then(s => setAiSummary(s)).catch(() => {}).finally(() => setAiLoading(false));
    } catch { setDetail(null); }
  }

  const filtered = soapSearch
    ? detail?.consultations.filter(c =>
        (c.soap_note.subjective + c.soap_note.assessment + (c.patient_summary || '')).toLowerCase().includes(soapSearch.toLowerCase())
      )
    : detail?.consultations;

  // Timeline chip colors based on type
  const chipStyles: Record<string, { bg: string; text: string; border: string; icon: string; label: string }> = {
    visit: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-100', icon: 'stethoscope', label: 'Visit' },
    labs: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-100', icon: 'biotech', label: 'Labs' },
    rx: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-100', icon: 'pill', label: 'Rx' },
    note: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-100', icon: 'note_alt', label: 'Note' },
  };

  function getChipType(c: Consultation): string {
    if (c.medication_changes && c.medication_changes.length > 0) return 'rx';
    if (c.flags && c.flags.length > 0) return 'note';
    return 'visit';
  }

  return (
    <div className="bg-slate-50 text-slate-900 min-h-screen flex flex-col">
      {/* ── Header ── */}
      <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-200 bg-white px-10 py-3 shadow-sm">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3 text-blue-600">
            <div className="size-8 bg-blue-600/10 flex items-center justify-center rounded-lg">
              <Icon name="medical_services" className="text-blue-600 text-xl" />
            </div>
            <h2 className="text-slate-900 text-xl font-bold leading-tight tracking-tight">AidCare</h2>
          </div>
          <label className="hidden md:flex flex-col min-w-40 max-w-64">
            <div className="flex w-full items-stretch rounded-lg h-10 ring-1 ring-slate-200 focus-within:ring-2 focus-within:ring-blue-600">
              <div className="text-slate-500 flex bg-slate-50 items-center justify-center pl-4 rounded-l-lg">
                <Icon name="search" className="text-xl" />
              </div>
              <input className="w-full min-w-0 flex-1 rounded-r-lg bg-slate-50 focus:outline-none border-none h-full placeholder:text-slate-400 px-4 pl-2 text-sm" placeholder="Search Patients" />
            </div>
          </label>
        </div>
        <div className="flex flex-1 justify-end gap-8 items-center">
          <nav className="hidden lg:flex items-center gap-8">
            <a className="text-slate-900 hover:text-blue-600 text-sm font-medium transition-colors cursor-pointer" onClick={() => router.push('/')}>Dashboard</a>
            <a className="text-slate-900 hover:text-blue-600 text-sm font-medium transition-colors cursor-pointer" onClick={() => router.push('/triage')}>Triage</a>
            <a className="text-slate-900 hover:text-blue-600 text-sm font-medium transition-colors cursor-pointer" onClick={() => router.push('/scribe')}>Scribe</a>
            <a className="text-blue-600 text-sm font-medium">Patients</a>
            <a className="text-slate-900 hover:text-blue-600 text-sm font-medium transition-colors cursor-pointer" onClick={() => router.push('/handover')}>Handover</a>
          </nav>
          <div className="flex items-center gap-4">
            <button className="relative flex items-center justify-center size-10 rounded-full hover:bg-slate-100 text-slate-600 transition-colors">
              <Icon name="notifications" />
              <span className="absolute top-2 right-2 size-2 bg-red-500 rounded-full border border-white" />
            </button>
            <div className="size-10 rounded-full bg-blue-600/10 flex items-center justify-center text-sm font-bold text-blue-600 ring-2 ring-slate-100">
              {user?.name.split(' ').map(n => n[0]).join('').slice(0, 2) || 'DR'}
            </div>
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Clinical Timeline ── */}
        <aside className="w-80 border-r border-slate-200 bg-white overflow-y-auto hidden md:flex flex-col flex-shrink-0">
          <div className="p-6 border-b border-slate-100 sticky top-0 bg-white z-10">
            <h3 className="text-slate-900 text-lg font-bold">Clinical Timeline</h3>
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Sort by Date</span>
              <button className="text-blue-600 hover:text-blue-700 transition-colors">
                <Icon name="filter_list" className="text-xl" />
              </button>
            </div>
          </div>
          <div className="p-4 flex flex-col gap-6 relative">
            {/* Timeline line */}
            <div className="absolute left-[29px] top-6 bottom-6 w-px bg-slate-200 z-0" />

            {detail?.consultations.map((c, i) => {
              const d = new Date(c.timestamp);
              const isToday = new Date().toDateString() === d.toDateString();
              const type = getChipType(c);
              const chip = chipStyles[type];
              return (
                <div key={c.consultation_id} className="relative z-10 pl-10 group cursor-pointer">
                  <div className={`absolute left-[9px] top-1 rounded-full ring-4 ring-white ${
                    isToday && i === 0 ? 'size-3 bg-blue-600' : 'size-2 bg-slate-300 group-hover:bg-blue-600 transition-colors'
                  }`} style={isToday && i === 0 ? { left: '9px' } : { left: '11px' }} />
                  <div className="flex flex-col gap-1">
                    <span className={`text-xs font-${isToday && i === 0 ? 'semibold' : 'medium'} ${isToday && i === 0 ? 'text-blue-600' : 'text-slate-500'}`}>
                      {isToday && i === 0 ? `Today, ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : d.toLocaleDateString([], { month: 'short', day: '2-digit', year: 'numeric' })}
                    </span>
                    <h4 className="text-sm font-semibold text-slate-700 group-hover:text-blue-600 transition-colors">
                      {c.patient_summary?.split('.')[0] || 'Consultation'}
                    </h4>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${chip.bg} ${chip.text} text-[10px] font-medium border ${chip.border}`}>
                        <Icon name={chip.icon} className="text-xs" /> {chip.label}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {(!detail || detail.consultations.length === 0) && !loading && (
              <p className="text-sm text-slate-400 text-center py-8">No clinical events yet.</p>
            )}
          </div>
        </aside>

        {/* ── MAIN Content ── */}
        <main className="flex-1 overflow-y-auto bg-slate-50 p-6 lg:p-10">
          {!detail && loading && <p className="text-slate-400 text-center py-16">Loading patients...</p>}
          {!detail && !loading && <p className="text-slate-400 text-center py-16">No patients found.</p>}

          {detail && (
            <div className="max-w-6xl mx-auto flex flex-col gap-8">
              {/* Breadcrumbs & actions */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2 text-sm">
                  <a className="text-slate-500 hover:text-blue-600 cursor-pointer" onClick={() => router.push('/patients')}>Patients</a>
                  <span className="text-slate-300">/</span>
                  <span className="text-slate-900 font-medium">{detail.full_name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <button className="hidden sm:flex items-center justify-center gap-2 h-9 px-4 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors">
                    <Icon name="print" className="text-lg" /> Print Record
                  </button>
                  <button onClick={() => router.push(`/scribe?patient=${detail.patient_id}`)}
                    className="flex items-center justify-center gap-2 h-9 px-4 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm shadow-blue-200">
                    <Icon name="add" className="text-lg" /> New Consultation
                  </button>
                </div>
              </div>

              {/* Patient header card */}
              <section className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
                <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between">
                  <div className="flex gap-5 items-center">
                    <div className="relative">
                      <div className="size-20 md:size-24 rounded-full bg-slate-100 flex items-center justify-center text-2xl font-bold text-slate-600 ring-4 ring-slate-50">
                        {detail.full_name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                      </div>
                      <span className="absolute bottom-1 right-1 size-4 bg-green-500 border-2 border-white rounded-full" />
                    </div>
                    <div>
                      <h1 className="text-slate-900 text-2xl md:text-3xl font-bold leading-tight">
                        {detail.full_name} <span className="text-lg font-medium text-slate-500 ml-1">({detail.age}{detail.gender?.charAt(0).toUpperCase()})</span>
                      </h1>
                      <div className="flex flex-wrap gap-x-6 gap-y-2 mt-2 text-sm text-slate-600">
                        <div className="flex items-center gap-1">
                          <Icon name="badge" className="text-lg text-slate-400" /> ID: #{detail.patient_id.slice(-5)}
                        </div>
                        {detail.admission_date && (
                          <div className="flex items-center gap-1">
                            <Icon name="calendar_today" className="text-lg text-slate-400" /> Admitted: {new Date(detail.admission_date).toLocaleDateString()}
                          </div>
                        )}
                        {detail.bed_number && (
                          <div className="flex items-center gap-1">
                            <Icon name="bed" className="text-lg text-slate-400" /> Bed {detail.bed_number}, {detail.ward_name}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  {detail.allergies && detail.allergies.length > 0 && (
                    <div className="px-4 py-3 bg-red-50 border border-red-100 rounded-lg flex flex-col justify-center min-w-[180px]">
                      <span className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-1">Critical Allergies</span>
                      <div className="flex items-center gap-2 text-red-800 text-sm font-medium">
                        <Icon name="warning" className="text-lg" /> {detail.allergies.join(', ')}
                      </div>
                    </div>
                  )}
                </div>

                {/* Vitals */}
                {detail.vitals && (
                  <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4 pt-6 border-t border-slate-100">
                    {detail.vitals.bp != null && (
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-slate-500 font-medium uppercase">Blood Pressure</span>
                        <div className="flex items-baseline gap-2">
                          <span className="text-xl md:text-2xl font-bold text-slate-900">{String(detail.vitals.bp)}</span>
                          <span className="text-xs font-medium text-green-600 bg-green-50 px-1.5 py-0.5 rounded flex items-center">
                            <Icon name="check" className="text-sm" /> Stable
                          </span>
                        </div>
                      </div>
                    )}
                    {detail.vitals.hr != null && (
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-slate-500 font-medium uppercase">Heart Rate</span>
                        <span className="text-xl md:text-2xl font-bold text-slate-900">{detail.vitals.hr} <span className="text-sm font-normal text-slate-500">bpm</span></span>
                      </div>
                    )}
                    {detail.vitals.temp != null && (
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-slate-500 font-medium uppercase">Temperature</span>
                        <span className="text-xl md:text-2xl font-bold text-slate-900">{detail.vitals.temp} <span className="text-sm font-normal text-slate-500">&deg;C</span></span>
                      </div>
                    )}
                    {detail.vitals.weight != null && (
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-slate-500 font-medium uppercase">Weight</span>
                        <span className="text-xl md:text-2xl font-bold text-slate-900">{detail.vitals.weight} <span className="text-sm font-normal text-slate-500">kg</span></span>
                      </div>
                    )}
                  </div>
                )}
              </section>

              {/* AI-Summarized History */}
              <section className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-100 shadow-sm relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <Icon name="auto_awesome" className="text-blue-600" style={{ fontSize: '120px' }} />
                </div>
                <div className="flex items-center gap-2 mb-4 relative z-10">
                  <div className="size-8 rounded-lg bg-white flex items-center justify-center shadow-sm text-blue-600">
                    <Icon name="auto_awesome" className="text-xl" />
                  </div>
                  <h2 className="text-lg font-bold text-slate-900">AI-Summarized History</h2>
                  <span className="ml-auto text-xs font-medium text-blue-600 bg-white/50 px-2 py-1 rounded backdrop-blur-sm">Powered by Gemini</span>
                </div>
                <div className="grid md:grid-cols-2 gap-6 relative z-10">
                  <div className="bg-white/60 backdrop-blur-sm rounded-lg p-4 border border-blue-100/50">
                    <h3 className="text-sm font-bold text-slate-800 mb-2 flex items-center gap-2">
                      <Icon name="update" className="text-lg text-blue-600" /> Chronic Conditions
                    </h3>
                    {aiLoading ? <p className="text-sm text-slate-500">Analyzing...</p> : (
                      <ul className="list-disc list-outside pl-4 space-y-2 text-sm text-slate-700">
                        {aiSummary && aiSummary.chronic_conditions.length > 0
                          ? aiSummary.chronic_conditions.map((cc, i) => <li key={i}><strong>{cc.condition}:</strong> {cc.details}</li>)
                          : <li className="text-slate-400">No chronic conditions identified.</li>
                        }
                      </ul>
                    )}
                  </div>
                  <div className="bg-white/60 backdrop-blur-sm rounded-lg p-4 border border-blue-100/50">
                    <h3 className="text-sm font-bold text-slate-800 mb-2 flex items-center gap-2">
                      <Icon name="warning" className="text-lg text-orange-500" /> Recent Flagged Patterns
                    </h3>
                    {aiLoading ? <p className="text-sm text-slate-500">Analyzing...</p> : (
                      <ul className="list-disc list-outside pl-4 space-y-2 text-sm text-slate-700">
                        {aiSummary && aiSummary.flagged_patterns.length > 0
                          ? aiSummary.flagged_patterns.map((f, i) => <li key={i}>{f}</li>)
                          : <li className="text-slate-400">No concerning patterns.</li>
                        }
                      </ul>
                    )}
                  </div>
                </div>
              </section>

              {/* SOAP History */}
              <section className="flex flex-col gap-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <h2 className="text-xl font-bold text-slate-900">Consultation History (SOAP)</h2>
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2">
                        <Icon name="search" className="text-slate-400 text-xl" />
                      </span>
                      <input value={soapSearch} onChange={e => setSoapSearch(e.target.value)}
                        className="pl-10 pr-4 py-2 h-10 rounded-lg border border-slate-200 bg-white text-sm focus:ring-2 focus:ring-blue-600 focus:border-transparent w-full sm:w-64"
                        placeholder="Search notes..." />
                    </div>
                    <button className="flex items-center gap-2 h-10 px-4 rounded-lg bg-white border border-slate-200 text-blue-600 font-medium text-sm hover:bg-blue-50 transition-colors">
                      <Icon name="show_chart" className="text-xl" /> Compare Vitals
                    </button>
                  </div>
                </div>

                <div className="flex flex-col gap-4">
                  {(filtered || []).map(c => {
                    const d = new Date(c.timestamp);
                    const type = getChipType(c);
                    return (
                      <div key={c.consultation_id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow cursor-pointer group">
                        <div className="flex justify-between items-start mb-3 border-b border-slate-100 pb-3">
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="text-lg font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                                {c.patient_summary?.split('.')[0] || 'Consultation'}
                              </h3>
                              <span className="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded font-medium border border-slate-200">
                                {type === 'visit' ? 'Outpatient' : type === 'rx' ? 'Prescription' : 'Follow-up'}
                              </span>
                            </div>
                            <p className="text-sm text-slate-500">
                              {d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
                              {c.doctor_name ? ` \u2022 ${c.doctor_name}` : ''}
                            </p>
                          </div>
                          <button className="text-slate-400 hover:text-blue-600">
                            <Icon name="chevron_right" />
                          </button>
                        </div>
                        <div className="grid md:grid-cols-4 gap-4 text-sm">
                          {(['subjective', 'objective', 'assessment', 'plan'] as const).map(s => (
                            <div key={s}>
                              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{s}</span>
                              <p className="text-slate-700 line-clamp-2">{c.soap_note[s] || '\u2014'}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="text-center py-6 text-slate-400 text-sm">
                  End of Records for Last 12 Months
                </div>
              </section>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
