'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Icon from '../../components/Icon';
import { transcribeAndScribe, getPatientDetail, startShift, getActiveShift, getError } from '../../lib/api';
import { getSessionUser, getSessionShift, setSessionShift } from '../../lib/session';
import { ScribeResult, PatientDetail, SOAPNote, Language } from '../../types';

interface TranscriptMsg {
  role: 'DR' | 'PT';
  content: string;
  time: string;
  pidgin?: boolean;
  tags?: string[];
}

type RecState = 'idle' | 'recording' | 'processing';

export default function ScribePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const patientId = searchParams.get('patient') || '';

  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [transcript, setTranscript] = useState<TranscriptMsg[]>([]);
  const [soap, setSoap] = useState<SOAPNote>({ subjective: '', objective: '', assessment: '', plan: '' });
  const [recState, setRecState] = useState<RecState>('idle');
  const [recTime, setRecTime] = useState(0);
  const [language, setLanguage] = useState<Language>('en');
  const [result, setResult] = useState<ScribeResult | null>(null);
  const [error, setError] = useState('');

  const mrRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const user = typeof window !== 'undefined' ? getSessionUser() : null;

  useEffect(() => {
    if (!user) { router.push('/login'); return; }
    ensureShift();
    if (patientId) loadPatient(patientId);
  }, [patientId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [transcript]);

  async function ensureShift() {
    if (getSessionShift()) return;
    try {
      const a = await getActiveShift();
      if (a.shift) setSessionShift({ shift_id: a.shift.shift_id, started_at: a.shift.started_at, ward_id: a.shift.ward_id, ward_name: a.shift.ward_name });
      else {
        const u = getSessionUser();
        const r = await startShift(u?.ward_id || undefined);
        setSessionShift({ shift_id: r.shift_id, started_at: r.started_at, ward_id: r.ward_id, ward_name: null });
      }
    } catch {}
  }

  async function loadPatient(id: string) { try { setPatient(await getPatientDetail(id)); } catch {} }

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mrRef.current = mr; chunksRef.current = [];
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.start(); setRecState('recording'); setRecTime(0);
      timerRef.current = setInterval(() => setRecTime(t => t + 1), 1000);
    } catch { setError('Microphone access denied.'); }
  }

  async function stopAndProcess() {
    setRecState('processing'); setError('');
    if (timerRef.current) clearInterval(timerRef.current);
    const blob = await new Promise<Blob>(resolve => {
      mrRef.current!.onstop = () => resolve(new Blob(chunksRef.current, { type: 'audio/webm' }));
      mrRef.current!.stop(); mrRef.current!.stream.getTracks().forEach(t => t.stop());
    });
    try {
      const res = await transcribeAndScribe(blob, patientId, patient?.full_name || 'Unknown', language);
      setResult(res); setSoap(res.soap_note);
      const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const sentences = res.transcript.split(/(?<=[.!?])\s+/).filter(Boolean);
      setTranscript(sentences.map((s, i) => ({
        role: i % 2 === 0 ? 'DR' : 'PT', content: s, time: now,
        pidgin: i % 2 === 1 && res.pidgin_detected, tags: [],
      })));
    } catch (err) { setError(getError(err)); }
    finally { setRecState('idle'); }
  }

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  return (
    <div className="min-h-screen bg-white text-slate-900 flex flex-col">
      {/* ── Top bar ── */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-200 bg-white shadow-sm sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push('/')} className="text-slate-400 hover:text-slate-700 transition">
            <Icon name="arrow_back" className="text-xl" />
          </button>
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-lg bg-blue-600/10 flex items-center justify-center">
              <Icon name="medical_services" className="text-blue-600 text-lg" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">AidCare Scribe</p>
              {patientId && <p className="text-[10px] text-slate-400">Session ID: #AC-{patientId.slice(-4).toUpperCase()}-LAG</p>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {recState === 'recording' && (
            <span className="flex items-center gap-1.5 text-xs font-semibold bg-red-50 text-red-600 px-3 py-1.5 rounded-full border border-red-100">
              <span className="size-2 rounded-full bg-red-500 animate-pulse" />
              RECORDING LIVE&nbsp;&nbsp;{fmt(recTime)}
            </span>
          )}
          <select value={language} onChange={e => setLanguage(e.target.value as Language)}
            className="h-9 rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:ring-2 focus:ring-blue-600 focus:border-transparent">
            <option value="en">English</option>
            <option value="pcm">Pidgin</option>
            <option value="ha">Hausa</option>
            <option value="yo">Yoruba</option>
            <option value="ig">Igbo</option>
          </select>
          <button className="text-slate-400 hover:text-slate-600"><Icon name="settings" className="text-xl" /></button>
          {user && (
            <div className="flex items-center gap-2">
              <div className="text-right text-xs">
                <p className="font-semibold text-slate-900">{user.name}</p>
                <p className="text-slate-400">{user.specialty || 'General Practitioner'}</p>
              </div>
              <div className="size-9 rounded-full bg-blue-600/10 flex items-center justify-center text-xs font-bold text-blue-600 ring-2 ring-slate-100">
                {user.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
              </div>
            </div>
          )}
        </div>
      </header>

      {/* ── 3-Panel Layout ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT: Patient Info ── */}
        <aside className="w-64 border-r border-slate-200 bg-white p-5 overflow-y-auto flex-shrink-0">
          {patient ? (
            <>
              {/* Avatar + Name */}
              <div className="flex items-center gap-3 mb-5">
                <div className="size-14 rounded-full bg-slate-100 flex items-center justify-center text-base font-bold text-slate-600 ring-2 ring-slate-50">
                  {patient.full_name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-900">{patient.full_name}</p>
                  <p className="text-xs text-slate-500">{patient.gender}, {patient.age} &bull; ID: #{patient.patient_id.slice(-6)}</p>
                </div>
              </div>

              {/* Vitals grid */}
              {patient.vitals && (
                <div className="grid grid-cols-2 gap-2 mb-5">
                  {Object.entries(patient.vitals).map(([k, v]) => (
                    <div key={k} className="bg-slate-50 rounded-lg p-3 text-center border border-slate-100">
                      <p className="text-[10px] text-slate-400 uppercase font-semibold tracking-wide">{k === 'bp' ? 'BP' : k === 'hr' ? 'HR' : k === 'temp' ? 'TEMP' : 'WEIGHT'}</p>
                      <p className="text-lg font-bold text-slate-900 mt-0.5">
                        {String(v)}{k === 'temp' ? '\u00b0' : ''}
                      </p>
                      <p className="text-[10px] text-slate-400">{k === 'bp' ? 'mmHg' : k === 'hr' ? 'bpm' : k === 'temp' ? 'Celsius' : 'kg'}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Medical History */}
              {patient.medical_history && patient.medical_history.length > 0 && (
                <div className="mb-5">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-bold text-slate-900">Medical History</p>
                    <button className="text-blue-600 text-xs font-medium">View Full</button>
                  </div>
                  {patient.medical_history.slice(0, 3).map((h, i) => (
                    <div key={i} className="mb-2.5 border-l-2 border-slate-200 pl-3">
                      <p className="text-xs font-semibold text-slate-800">{h.condition}</p>
                      {h.date && <p className="text-[10px] text-slate-400">{h.date}</p>}
                      {h.notes && <p className="text-[10px] text-slate-500">{h.notes}</p>}
                    </div>
                  ))}
                </div>
              )}

              {/* Allergies */}
              {patient.allergies && patient.allergies.length > 0 && (
                <div className="mb-5">
                  <p className="text-xs font-bold text-slate-900 mb-2">Allergies</p>
                  <div className="flex flex-wrap gap-1.5">
                    {patient.allergies.map((a, i) => (
                      <span key={i} className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-red-50 text-red-700 border border-red-100">{a}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Active Medications */}
              {patient.active_medications && patient.active_medications.length > 0 && (
                <div>
                  <p className="text-xs font-bold text-slate-900 mb-2">Active Medications</p>
                  {patient.active_medications.map((m, i) => (
                    <div key={i} className="flex items-center gap-2 mb-1.5 text-xs">
                      <Icon name="pill" className="text-sm text-slate-400" />
                      <span className="text-slate-800 font-medium">{m.name}</span>
                      <span className="text-slate-400">{m.dose}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-16">
              <Icon name="person_search" className="text-4xl text-slate-300 mb-3" />
              <p className="text-sm text-slate-400 mb-2">No patient selected</p>
              <button onClick={() => router.push('/patients')} className="text-xs text-blue-600 hover:underline">Select a patient</button>
            </div>
          )}
        </aside>

        {/* ── CENTER: Live Transcript ── */}
        <div className="flex-1 flex flex-col border-r border-slate-200 bg-white">
          <div className="px-6 py-3 border-b border-slate-200 flex items-center gap-3">
            <Icon name="record_voice_over" className="text-lg text-slate-400" />
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Live Consultation Transcript</h2>
            {result?.pidgin_detected && (
              <span className="ml-2 text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-100 flex items-center gap-1">
                <span className="size-1.5 rounded-full bg-green-500" /> AI Listening (Pidgin/English)
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5 bg-slate-50">
            <div className="max-w-2xl mx-auto space-y-5">
              {transcript.length > 0 ? transcript.map((msg, i) => (
                <div key={i} className="flex gap-3">
                  <div className={`size-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 text-white ${
                    msg.role === 'DR' ? 'bg-blue-600' : 'bg-slate-500'
                  }`}>
                    {msg.role}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] text-slate-400 mb-1">{msg.time}</p>
                    <p className="text-sm text-slate-800 leading-relaxed">{msg.content}</p>
                    {msg.pidgin && (
                      <span className="inline-flex items-center gap-1 mt-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-100">
                        <Icon name="translate" className="text-xs" /> Pidgin Detected
                      </span>
                    )}
                    {msg.tags?.map((tag, j) => (
                      <span key={j} className="inline-flex items-center gap-1 mt-1.5 ml-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-100">
                        <Icon name="check_circle" className="text-xs" /> {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )) : (
                <div className="flex flex-col items-center justify-center h-full py-20 text-slate-400">
                  <div className="size-20 rounded-full bg-blue-50 flex items-center justify-center mb-4">
                    <Icon name="mic" className="text-4xl text-blue-300" />
                  </div>
                  <p className="text-lg font-semibold text-slate-700 mb-1">Start Consultation</p>
                  <p className="text-sm text-slate-400">Ensure the microphone is positioned correctly before beginning.</p>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          {error && <div className="mx-6 mb-3 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</div>}

          {/* Controls */}
          <div className="py-4 flex items-center justify-center gap-4 border-t border-slate-200 bg-white">
            {recState === 'idle' && (
              <>
                <button className="size-10 rounded-full border border-slate-200 bg-slate-50 flex items-center justify-center text-slate-400 hover:bg-slate-100 transition">
                  <Icon name="pause" className="text-lg" />
                </button>
                <button onClick={startRec} className="size-14 rounded-full bg-red-500 hover:bg-red-600 transition flex items-center justify-center shadow-lg shadow-red-200">
                  <Icon name="mic" className="text-white text-2xl" />
                </button>
                <button className="size-10 rounded-full border border-slate-200 bg-slate-50 flex items-center justify-center text-slate-400 hover:bg-slate-100 transition">
                  <Icon name="format_list_bulleted" className="text-lg" />
                </button>
              </>
            )}
            {recState === 'recording' && (
              <>
                <button className="size-10 rounded-full border border-slate-200 bg-slate-50 flex items-center justify-center text-slate-500 hover:bg-slate-100 transition">
                  <Icon name="pause" className="text-lg" />
                </button>
                <button onClick={stopAndProcess} className="size-14 rounded-full bg-red-500 hover:bg-red-600 transition flex items-center justify-center shadow-lg shadow-red-200 animate-pulse">
                  <Icon name="stop" className="text-white text-2xl" />
                </button>
                <button className="size-10 rounded-full border border-slate-200 bg-slate-50 flex items-center justify-center text-slate-400 hover:bg-slate-100 transition">
                  <Icon name="format_list_bulleted" className="text-lg" />
                </button>
              </>
            )}
            {recState === 'processing' && (
              <div className="flex items-center gap-3 text-blue-600">
                <div className="size-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm font-medium">Processing audio and generating SOAP note...</span>
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: Auto-Generated SOAP ── */}
        <aside className="w-80 flex-shrink-0 flex flex-col overflow-hidden bg-white">
          <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Icon name="auto_awesome" className="text-lg text-amber-500" /> Auto-Generated SOAP
            </h2>
            {result && <button className="text-blue-600 text-xs font-medium hover:underline">Regenerate</button>}
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {([
              { key: 'subjective' as const, label: 'SUBJECTIVE (S)' },
              { key: 'objective' as const, label: 'OBJECTIVE (O)' },
              { key: 'assessment' as const, label: 'ASSESSMENT (A)' },
              { key: 'plan' as const, label: 'PLAN (P)' },
            ]).map(section => (
              <div key={section.key}>
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">{section.label}</h3>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  {soap[section.key] ? (
                    <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{soap[section.key]}</p>
                  ) : (
                    <p className="text-sm text-slate-400 italic">Will be generated from recording...</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-slate-200">
            <button disabled={!result}
              className={`w-full py-3 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition ${
                result
                  ? 'bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-200'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              }`}>
              <Icon name="draw" className="text-lg" /> Review &amp; Sign Note
            </button>
            <p className="text-[10px] text-slate-400 text-center mt-2">
              By signing, you confirm accuracy of the generated note.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
