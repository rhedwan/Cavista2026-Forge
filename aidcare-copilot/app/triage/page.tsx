'use client';

import { useEffect, useRef, useState } from 'react';
import AppShell from '../../components/AppShell';
import Icon from '../../components/Icon';
import { triageContinue, triageProcessText, triageProcessAudio, triageTTS, triageSave, getPatients, getError } from '../../lib/api';
import { Patient } from '../../types';

type Phase = 'language' | 'conversation' | 'results';
type Lang = 'en' | 'ha' | 'yo' | 'ig' | 'pcm';
type RecState = 'idle' | 'recording' | 'processing';

interface Msg {
  role: 'patient' | 'ai' | 'staff';
  content: string;
}

const LANGS: { code: Lang; name: string; native: string; greeting: string; color: string }[] = [
  { code: 'en', name: 'English', native: 'English', greeting: 'Hello! How are you feeling today?', color: '#2563eb' },
  { code: 'ha', name: 'Hausa', native: 'هَوُسَ', greeting: 'Sannu! Yaya zan iya taimaka maka yau?', color: '#059669' },
  { code: 'yo', name: 'Yoruba', native: 'Yorùbá', greeting: 'Bawo ni! Kini mo le se fun e loni?', color: '#7c3aed' },
  { code: 'ig', name: 'Igbo', native: 'Igbo', greeting: 'Ndewo! Kedu otu m ga-esi nyere gi aka taa?', color: '#dc2626' },
  { code: 'pcm', name: 'Pidgin', native: 'Naija Pidgin', greeting: 'How far! Wetin dey do you today?', color: '#d97706' },
];

const RISK: Record<string, { color: string; bg: string }> = {
  high: { color: '#dc2626', bg: '#fef2f2' },
  moderate: { color: '#d97706', bg: '#fffbeb' },
  low: { color: '#059669', bg: '#ecfdf5' },
};

export default function TriagePage() {
  const [phase, setPhase] = useState<Phase>('language');
  const [lang, setLang] = useState<Lang>('en');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [staffNote, setStaffNote] = useState('');
  const [staffNotes, setStaffNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [triageResult, setTriageResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [patients, setPatients] = useState<Patient[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [recState, setRecState] = useState<RecState>('idle');
  const [recTime, setRecTime] = useState(0);
  const mrRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  function selectLang(code: Lang) {
    setLang(code);
    const l = LANGS.find(x => x.code === code)!;
    setMsgs([{ role: 'ai', content: l.greeting }]);
    setPhase('conversation');
    playTTS(l.greeting, code);
  }

  async function playTTS(text: string, l: string) {
    try {
      const blob = await triageTTS(text, l);
      const audio = new Audio(URL.createObjectURL(blob));
      audio.play().catch(() => {});
    } catch {}
  }

  function buildHistory() {
    return msgs.filter(m => m.role !== 'staff').map(m => m.role === 'patient' ? `PATIENT: ${m.content}` : `YOU: ${m.content}`).join('\n');
  }

  async function send(text: string) {
    if (!text.trim()) return;
    const newMsgs: Msg[] = [...msgs, { role: 'patient', content: text }];
    setMsgs(newMsgs);
    setInput('');
    setLoading(true);
    setError('');
    try {
      const res = await triageContinue({ conversation_history: buildHistory(), patient_message: text, staff_notes: staffNotes, language: lang });
      const aiMsg: Msg = { role: 'ai', content: res.response };
      setMsgs([...newMsgs, aiMsg]);
      playTTS(res.response, lang);
      if (res.should_auto_complete) setTimeout(() => completeAssessment([...newMsgs, aiMsg]), 1500);
    } catch (err) { setError(getError(err)); }
    finally { setLoading(false); }
  }

  function addStaff() {
    if (!staffNote.trim()) return;
    const note = staffNote.trim();
    setStaffNotes(p => p ? `${p}\n${note}` : note);
    setMsgs([...msgs, { role: 'staff', content: note }]);
    setStaffNote('');
  }

  async function completeAssessment(m?: Msg[]) {
    const all = m || msgs;
    const text = all.map(x => x.role === 'staff' ? `STAFF: ${x.content}` : x.role === 'patient' ? `PATIENT: ${x.content}` : `ASSISTANT: ${x.content}`).join('\n');
    setLoading(true);
    setError('');
    try {
      const res = await triageProcessText(text, lang, staffNotes);
      setTriageResult(res);
      setPhase('results');
    } catch (err) { setError(getError(err)); }
    finally { setLoading(false); }
  }

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mrRef.current = mr; chunksRef.current = [];
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.start();
      setRecState('recording');
      setRecTime(0);
      timerRef.current = setInterval(() => setRecTime(t => t + 1), 1000);
    } catch { setError('Microphone access denied.'); }
  }

  async function stopRec() {
    if (!mrRef.current) return;
    setRecState('processing');
    if (timerRef.current) clearInterval(timerRef.current);
    const blob = await new Promise<Blob>(resolve => {
      mrRef.current!.onstop = () => resolve(new Blob(chunksRef.current, { type: 'audio/webm' }));
      mrRef.current!.stop();
      mrRef.current!.stream.getTracks().forEach(t => t.stop());
    });
    try {
      const res = await triageProcessAudio(blob, lang, staffNotes);
      if (res.transcript) setMsgs(prev => [...prev, { role: 'patient', content: String(res.transcript) }]);
      setTriageResult(res);
      setPhase('results');
    } catch (err) { setError(getError(err)); }
    finally { setRecState('idle'); }
  }

  async function openPicker() {
    setShowPicker(true);
    try { const d = await getPatients(); setPatients([...d.patients.critical, ...d.patients.stable, ...d.patients.discharged]); } catch {}
  }

  async function assignTo(uuid: string) {
    if (!triageResult) return;
    try { await triageSave(uuid, triageResult); setShowPicker(false); } catch (err) { setError(getError(err)); }
  }

  function reset() { setPhase('language'); setMsgs([]); setStaffNotes(''); setStaffNote(''); setTriageResult(null); setError(''); setInput(''); }

  const rec = triageResult?.triage_recommendation as Record<string, unknown> | undefined;
  const risk = (triageResult?.risk_level as string) || 'low';
  const symptoms = (triageResult?.extracted_symptoms as string[]) || [];
  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  return (
    <AppShell>
      <main className="flex-1 overflow-auto">
        {/* LANGUAGE SELECT */}
        {phase === 'language' && (
          <div className="max-w-3xl mx-auto py-16 px-6 text-center">
            <div className="inline-flex items-center justify-center size-14 rounded-2xl bg-primary/10 mb-4">
              <Icon name="stethoscope" className="text-primary text-3xl" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">Patient Triage</h1>
            <p className="text-sm text-slate-500 mb-8">Select the patient&apos;s preferred language to begin.</p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {LANGS.map(l => (
                <button key={l.code} onClick={() => selectLang(l.code)}
                  className="bg-white rounded-xl border border-slate-200 p-5 text-center hover:shadow-md hover:border-slate-300 transition-all group">
                  <p className="text-lg font-bold mb-1" style={{ color: l.color }}>{l.native}</p>
                  <p className="text-xs text-slate-500">{l.name}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* CONVERSATION */}
        {phase === 'conversation' && (
          <div className="flex h-[calc(100vh-57px)]">
            <div className="flex-1 flex flex-col">
              <div className="px-6 py-3 border-b border-slate-200 flex items-center justify-between bg-white">
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-semibold text-slate-900">Triage Conversation</h2>
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border"
                    style={{ color: LANGS.find(x => x.code === lang)?.color, borderColor: `${LANGS.find(x => x.code === lang)?.color}30`, background: `${LANGS.find(x => x.code === lang)?.color}08` }}>
                    {LANGS.find(x => x.code === lang)?.name}
                  </span>
                </div>
                <button onClick={() => completeAssessment()} disabled={msgs.length < 3 || loading}
                  className="h-9 px-4 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition disabled:opacity-40 shadow-sm shadow-blue-200">
                  Complete Assessment
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-6 py-5 bg-slate-50">
                <div className="max-w-2xl mx-auto space-y-4">
                  {msgs.map((m, i) => (
                    <div key={i} className={`flex gap-3 ${m.role === 'patient' ? 'flex-row-reverse' : ''}`}>
                      <div className={`size-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 text-white ${
                        m.role === 'patient' ? 'bg-primary' : m.role === 'staff' ? 'bg-amber-500' : 'bg-emerald-600'
                      }`}>
                        {m.role === 'patient' ? 'PT' : m.role === 'staff' ? 'RN' : 'AI'}
                      </div>
                      <div className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                        m.role === 'patient' ? 'bg-primary text-white rounded-tr-sm' :
                        m.role === 'staff' ? 'bg-amber-50 text-slate-800 border border-amber-200 rounded-tl-sm' :
                        'bg-white text-slate-800 border border-slate-200 rounded-tl-sm shadow-sm'
                      }`}>
                        {m.role === 'staff' && <p className="text-[10px] font-semibold text-amber-600 uppercase mb-1">Staff Note</p>}
                        {m.content}
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex gap-3">
                      <div className="size-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs font-bold text-white">AI</div>
                      <div className="bg-white border border-slate-200 rounded-xl px-4 py-3 shadow-sm">
                        <div className="flex gap-1.5">
                          <span className="size-2 rounded-full bg-slate-300 animate-bounce" />
                          <span className="size-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '0.15s' }} />
                          <span className="size-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '0.3s' }} />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={chatEnd} />
                </div>
              </div>

              {error && <div className="mx-6 mb-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</div>}

              <div className="px-6 py-3 border-t border-slate-200 bg-white flex gap-2">
                {recState === 'idle' ? (
                  <>
                    <input value={input} onChange={e => setInput(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && !loading && send(input)}
                      placeholder="Type patient's words..."
                      className="flex-1 h-10 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm focus:ring-2 focus:ring-primary focus:border-transparent" disabled={loading} />
                    <button onClick={startRec} className="size-10 rounded-lg bg-red-500 hover:bg-red-600 flex items-center justify-center text-white transition shadow-sm">
                      <Icon name="mic" className="text-lg" />
                    </button>
                    <button onClick={() => send(input)} disabled={!input.trim() || loading}
                      className="h-10 px-4 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition disabled:opacity-40">
                      Send
                    </button>
                  </>
                ) : recState === 'recording' ? (
                  <div className="flex items-center gap-3 flex-1">
                    <span className="flex items-center gap-1.5 text-sm text-red-600">
                      <span className="size-2 rounded-full bg-red-500 animate-pulse" />
                      Recording {fmt(recTime)}
                    </span>
                    <button onClick={stopRec} className="ml-auto h-10 px-4 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition">
                      Stop &amp; Process
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm text-slate-500 flex-1">
                    <div className="size-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    Processing audio...
                  </div>
                )}
              </div>
            </div>

            {/* Staff panel */}
            <div className="w-72 flex-shrink-0 border-l border-slate-200 bg-white flex flex-col hidden lg:flex">
              <div className="p-4 border-b border-slate-200">
                <h3 className="text-sm font-semibold text-slate-900 mb-1">Staff Clinical Notes</h3>
                <p className="text-xs text-slate-500">Add vitals, observations. Not spoken to patient.</p>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {staffNotes.split('\n').filter(Boolean).map((n, i) => (
                  <div key={i} className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-slate-700">{n}</div>
                ))}
              </div>
              <div className="p-4 border-t border-slate-200 flex gap-2">
                <input value={staffNote} onChange={e => setStaffNote(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addStaff()}
                  placeholder="e.g. BP 90/60, temp 39.2"
                  className="flex-1 h-9 rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs focus:ring-2 focus:ring-primary focus:border-transparent" />
                <button onClick={addStaff} disabled={!staffNote.trim()}
                  className="h-9 px-3 rounded-lg bg-slate-100 text-slate-600 text-xs font-medium hover:bg-slate-200 transition disabled:opacity-40">
                  Add
                </button>
              </div>
            </div>
          </div>
        )}

        {/* RESULTS */}
        {phase === 'results' && triageResult && (
          <div className="max-w-3xl mx-auto py-8 px-6">
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-2xl font-bold text-slate-900">Triage Assessment</h1>
              <button onClick={reset} className="h-9 px-4 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 transition">
                New Triage
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-white rounded-xl border border-slate-200 p-5 text-center">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Urgency Level</p>
                <p className="text-lg font-bold" style={{ color: RISK[risk]?.color }}>{(rec?.urgency_level as string) || 'Unknown'}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5 text-center">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Risk Level</p>
                <span className="inline-block text-sm font-bold px-4 py-1.5 rounded-full text-white uppercase"
                  style={{ background: RISK[risk]?.color }}>{risk}</span>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">Summary</h3>
              <p className="text-sm text-slate-700">{(rec?.summary_of_findings as string) || 'No summary.'}</p>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Extracted Symptoms</h3>
                <div className="flex flex-wrap gap-2">
                  {symptoms.length > 0 ? symptoms.map((s, i) => (
                    <span key={i} className="text-xs font-medium px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100">{s}</span>
                  )) : <p className="text-sm text-slate-400">None</p>}
                </div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Recommended Actions</h3>
                <ul className="space-y-1.5 text-sm text-slate-700">
                  {((rec?.recommended_actions_for_chw as string[]) || []).map((a, i) => (
                    <li key={i} className="flex gap-2"><span className="text-primary font-bold">{i + 1}.</span>{a}</li>
                  ))}
                </ul>
              </div>
            </div>

            {staffNotes && (
              <div className="bg-amber-50 rounded-xl border border-amber-200 p-5 mb-4">
                <h3 className="text-sm font-semibold text-slate-900 mb-2">Staff Notes</h3>
                <p className="text-sm text-slate-700 whitespace-pre-line">{staffNotes}</p>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              {risk === 'high' && (
                <a href="tel:112" className="h-10 px-5 rounded-lg bg-red-500 text-white text-sm font-medium flex items-center gap-2 hover:bg-red-600 transition">
                  <Icon name="call" className="text-lg" /> Call Emergency (112)
                </a>
              )}
              <button onClick={openPicker} className="h-10 px-5 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition shadow-sm shadow-blue-200">
                Assign to Patient Record
              </button>
            </div>

            {showPicker && (
              <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50" onClick={() => setShowPicker(false)}>
                <div className="bg-white rounded-xl shadow-xl p-6 w-96 max-h-[70vh] overflow-y-auto border border-slate-200" onClick={e => e.stopPropagation()}>
                  <h3 className="text-base font-semibold text-slate-900 mb-4">Select Patient</h3>
                  {patients.length > 0 ? (
                    <div className="space-y-2">
                      {patients.map(p => (
                        <button key={p.patient_id} onClick={() => assignTo(p.patient_id)}
                          className="w-full text-left rounded-lg border border-slate-200 p-3 hover:bg-slate-50 hover:border-slate-300 transition">
                          <p className="text-sm font-medium text-slate-900">{p.full_name}</p>
                          <p className="text-xs text-slate-500">{p.bed_number ? `Bed ${p.bed_number} \u2022 ` : ''}{p.primary_diagnosis || ''}</p>
                        </button>
                      ))}
                    </div>
                  ) : <p className="text-sm text-slate-400">No patients found.</p>}
                  <button onClick={() => setShowPicker(false)} className="mt-4 w-full h-9 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 transition">Cancel</button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </AppShell>
  );
}
