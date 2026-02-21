'use client';

import { useState } from 'react';
import AppShell from '../../components/AppShell';
import Icon from '../../components/Icon';
import { generateHandover, getError } from '../../lib/api';
import { getSessionShift, getSessionUser } from '../../lib/session';
import { HandoverReport } from '../../types';

export default function HandoverPage() {
  const [report, setReport] = useState<HandoverReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState('');

  const shift = typeof window !== 'undefined' ? getSessionShift() : null;
  const user = typeof window !== 'undefined' ? getSessionUser() : null;

  async function generate() {
    if (!shift) { setError('No active shift. Start a shift first.'); return; }
    setLoading(true);
    setError('');
    try {
      const r = await generateHandover(shift.shift_id, user?.ward_id || undefined, notes);
      setReport(r);
    } catch (err) { setError(getError(err)); }
    finally { setLoading(false); }
  }

  return (
    <AppShell>
      <main className="flex-1 overflow-y-auto bg-slate-50">
        {!report ? (
          <div className="max-w-lg mx-auto py-16 px-6 text-center">
            <div className="inline-flex items-center justify-center size-14 rounded-2xl bg-primary/10 mb-4">
              <Icon name="swap_horiz" className="text-primary text-3xl" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">Generate Handover Report</h1>
            <p className="text-sm text-slate-500 mb-6">
              {shift ? 'Generate a shift handover summary for the incoming team.' : 'You need an active shift to generate a handover.'}
            </p>
            {shift && (
              <div className="text-left bg-white rounded-xl border border-slate-200 p-5 mb-6">
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Additional Handover Notes (optional)</label>
                <textarea value={notes} onChange={e => setNotes(e.target.value)}
                  className="w-full h-24 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-primary focus:border-transparent"
                  placeholder="Any additional notes for the incoming team..." />
              </div>
            )}
            {error && <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2 mb-4">{error}</div>}
            <button onClick={generate} disabled={loading || !shift}
              className="h-10 px-6 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition disabled:opacity-40 shadow-sm shadow-blue-200">
              {loading ? 'Generating...' : 'Generate Report'}
            </button>
          </div>
        ) : (
          <>
            {/* Print bar */}
            <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
              <button onClick={() => setReport(null)} className="text-sm text-slate-500 hover:text-primary flex items-center gap-1">
                <Icon name="arrow_back" className="text-lg" /> Back to Dashboard
              </button>
              <div className="flex items-center gap-3">
                <button onClick={() => window.print()} className="h-9 px-4 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 transition flex items-center gap-2">
                  <Icon name="print" className="text-lg" /> Print
                </button>
                <button className="h-9 px-4 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 transition flex items-center gap-2">
                  <Icon name="download" className="text-lg" /> Export PDF
                </button>
              </div>
            </div>

            {/* Report */}
            <div className="max-w-3xl mx-auto py-8 px-6">
              {/* Header */}
              <div className="bg-white rounded-xl border border-slate-200 p-8 mb-6 shadow-sm">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="size-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                      <Icon name="medical_services" className="text-xl" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900">AidCare</h2>
                      <p className="text-xs text-slate-500">Medical Handover Report</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-slate-900">{user?.hospital_name || 'Hospital'}</p>
                    <p className="text-xs text-slate-500">{report.ward_name || user?.ward_name || 'Ward'}</p>
                  </div>
                </div>

                <div className="border-t border-slate-100 pt-5">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-1">Report Details</p>
                  <h1 className="text-2xl font-bold text-slate-900 mb-3">Shift Handover Summary</h1>
                  <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-slate-600">
                    <span className="flex items-center gap-1.5">
                      <Icon name="calendar_today" className="text-lg text-slate-400" />
                      {new Date(report.generated_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Icon name="schedule" className="text-lg text-slate-400" />
                      {report.shift_summary.start ? new Date(report.shift_summary.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '?'}
                      {' \u2013 '}
                      {report.shift_summary.end ? new Date(report.shift_summary.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Now'}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Icon name="person" className="text-lg text-slate-400" />
                      {report.doctor_name}
                    </span>
                  </div>
                </div>
              </div>

              {/* Critical */}
              {report.critical_patients.length > 0 && (
                <div className="mb-6">
                  <h2 className="text-base font-bold text-red-600 flex items-center gap-2 mb-3">
                    <Icon name="warning" className="text-xl" /> Critical Attention ({report.critical_patients.length})
                  </h2>
                  <div className="space-y-3">
                    {report.critical_patients.map((p, i) => (
                      <div key={i} className="bg-white rounded-xl border border-red-100 p-5 shadow-sm">
                        <div className="flex flex-col md:flex-row gap-4">
                          <div className="md:w-40 flex-shrink-0">
                            <p className="text-base font-bold text-slate-900">{p.patient_ref}</p>
                            <span className="inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-100">
                              {p.flags?.[0] || 'Critical'}
                            </span>
                          </div>
                          <div className="flex-1">
                            <p className="text-xs font-semibold text-slate-400 uppercase mb-1">AI Condition Summary</p>
                            <p className="text-sm text-slate-700 mb-3">{p.summary}</p>
                            {p.medication_changes && p.medication_changes.length > 0 && (
                              <div className="mb-2">
                                <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Key Medications</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {p.medication_changes.map((m, j) => (
                                    <span key={j} className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">{m.drug}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                          <div className="md:w-52 flex-shrink-0">
                            <p className="text-xs font-semibold text-red-600 uppercase mb-1">Action Items</p>
                            <ul className="text-sm text-slate-700 space-y-1">
                              {(p.flags || []).map((f, j) => (
                                <li key={j} className="flex gap-1.5"><span className="text-red-500">&bull;</span> {f}</li>
                              ))}
                              {p.action_required && <li className="flex gap-1.5"><span className="text-red-500">&bull;</span> {p.action_required}</li>}
                            </ul>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Stable */}
              {report.stable_patients.length > 0 && (
                <div className="mb-6">
                  <h2 className="text-base font-bold text-emerald-600 flex items-center gap-2 mb-3">
                    <Icon name="check_circle" className="text-xl" /> Stable Monitoring ({report.stable_patients.length})
                  </h2>
                  <div className="space-y-3">
                    {report.stable_patients.map((p, i) => (
                      <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm flex flex-col md:flex-row gap-4">
                        <div className="md:w-40 flex-shrink-0">
                          <p className="text-base font-bold text-slate-900">{p.patient_ref}</p>
                        </div>
                        <div className="flex-1">
                          <p className="text-xs font-semibold text-slate-400 uppercase mb-1">AI Condition Summary</p>
                          <p className="text-sm text-slate-700">{p.summary}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Discharged */}
              {report.discharged_patients.length > 0 && (
                <div className="mb-6">
                  <h2 className="text-base font-bold text-slate-600 flex items-center gap-2 mb-3">
                    <Icon name="logout" className="text-xl" /> Pending Discharge ({report.discharged_patients.length})
                  </h2>
                  <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                    <table className="w-full text-sm">
                      <thead><tr className="border-b border-slate-100 text-xs text-slate-400 uppercase">
                        <th className="text-left p-3 font-semibold">Patient</th>
                        <th className="text-left p-3 font-semibold">Status Note</th>
                      </tr></thead>
                      <tbody>
                        {report.discharged_patients.map((p, i) => (
                          <tr key={i} className="border-b border-slate-50 last:border-0">
                            <td className="p-3 font-medium text-slate-900">{p.patient_ref}</td>
                            <td className="p-3 text-slate-600">{p.summary}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Unit summary */}
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm mb-8">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-slate-400 font-semibold">Unit Fatigue Summary</p>
                    <p className="text-xs text-slate-500 mt-0.5">Based on admission volume &amp; acuity</p>
                  </div>
                  <div className="flex items-center gap-6 text-center">
                    <div><p className="text-xl font-bold text-slate-900">{report.shift_summary.patients_seen}</p><p className="text-[10px] text-slate-400 uppercase">Seen</p></div>
                    <div><p className="text-xl font-bold text-red-600">{report.critical_patients.length}</p><p className="text-[10px] text-slate-400 uppercase">Critical</p></div>
                    <div><p className="text-xl font-bold text-slate-600">{report.discharged_patients.length}</p><p className="text-[10px] text-slate-400 uppercase">Discharging</p></div>
                  </div>
                </div>
              </div>

              {/* Signatures */}
              <div className="grid grid-cols-2 gap-8 mb-8">
                <div className="border-t-2 border-slate-300 pt-3">
                  <p className="text-sm font-semibold text-slate-900">Outgoing Doctor Signature</p>
                  <p className="text-xs text-slate-400">Time: ________</p>
                </div>
                <div className="border-t-2 border-slate-300 pt-3">
                  <p className="text-sm font-semibold text-slate-900">Incoming Doctor Signature</p>
                  <p className="text-xs text-slate-400">Time: ________</p>
                </div>
              </div>

              <p className="text-center text-xs text-slate-400">
                Generated by AidCare System &bull; Confidential Patient Information &bull; Do Not Distribute Unauthorized Copies
              </p>
            </div>
          </>
        )}
      </main>
    </AppShell>
  );
}
