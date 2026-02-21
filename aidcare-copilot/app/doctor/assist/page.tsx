'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  copilotContinueConversation,
  copilotProcessAudio,
  copilotProcessText,
  getCopilotGuidelineSources,
  getErrorMessage,
} from '../../../lib/api';
import { ASSIST_LANGUAGES, ASSIST_LANGUAGE_ORDER } from '../../../lib/languages';
import { speakText, stopCurrentAudio } from '../../../lib/tts';
import {
  AssistLanguageCode,
  AssistMessage,
  AssistPhase,
  AssistRecordingState,
  AssistRiskLevel,
  AssistTriageResult,
} from '../../../types/triage';
import { getSessionDoctor } from '../../../lib/session';

const RISK_PANEL: Record<AssistRiskLevel, string> = {
  high:     'hospital-risk-high',
  moderate: 'hospital-risk-moderate',
  low:      'hospital-risk-low',
};

const RISK_CHIP: Record<AssistRiskLevel, string> = {
  high:     'hospital-chip hospital-chip-danger',
  moderate: 'hospital-chip hospital-chip-warning',
  low:      'hospital-chip hospital-chip-success',
};

const RISK_LABEL: Record<AssistRiskLevel, string> = {
  high: 'High Risk',
  moderate: 'Moderate',
  low: 'Low Risk',
};

const LANG_DOT: Record<AssistLanguageCode, string> = {
  en:  '#2563eb',
  ha:  '#059669',
  yo:  '#7c3aed',
  ig:  '#dc2626',
  pcm: '#d97706',
};

// ── SVG icons ─────────────────────────────────────────────────────────────────
const IcoBack = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
  </svg>
);
const IcoReset = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);
const IcoMic = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
  </svg>
);
const IcoSpeaker = () => (
  <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M12 6v12m-3.536-9.536a5 5 0 000 7.072" />
  </svg>
);
const IcoCheck = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
  </svg>
);
const IcoSend = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
  </svg>
);
const IcoPin = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);
const IcoArrow = () => (
  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
  </svg>
);
const IcoBot = () => (
  <svg width="15" height="15" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
  </svg>
);

export default function DoctorAssistPage() {
  const router = useRouter();
  const doctor = getSessionDoctor();

  const [phase, setPhase]                             = useState<AssistPhase>('language_select');
  const [language, setLanguage]                       = useState<AssistLanguageCode>('en');
  const [messages, setMessages]                       = useState<AssistMessage[]>([]);
  const [conversationContext, setConversationContext] = useState<string[]>([]);
  const [inputText, setInputText]                     = useState('');
  const [loading, setLoading]                         = useState(false);
  const [autoCompleting, setAutoCompleting]           = useState(false);
  const [error, setError]                             = useState('');
  const [result, setResult]                           = useState<AssistTriageResult | null>(null);
  const [sources, setSources]                         = useState<{ chw: number; clinical: number; parsed_guidelines: number } | null>(null);
  const [speaking, setSpeaking]                       = useState(false);
  const [recordingState, setRecordingState]           = useState<AssistRecordingState>('idle');
  const [audioBlob, setAudioBlob]                     = useState<Blob | null>(null);
  const [recordingTime, setRecordingTime]             = useState(0);

  const mediaRecorderRef  = useRef<MediaRecorder | null>(null);
  const audioChunksRef    = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const messagesEndRef    = useRef<HTMLDivElement>(null);

  const lang = ASSIST_LANGUAGES[language];

  useEffect(() => { if (!doctor) router.replace('/doctor'); }, [doctor, router]);
  useEffect(() => { getCopilotGuidelineSources().then((d) => setSources(d.sources)).catch(() => null); }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => () => {
    stopCurrentAudio();
    if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
  }, []);

  if (!doctor) return null;

  // ── Handlers ────────────────────────────────────────────────────────────────
  function beginConversation() {
    setPhase('conversation');
    setMessages([{ role: 'assistant', content: lang.greeting }]);
    setConversationContext([]);
    setInputText('');
    setResult(null);
    setError('');
  }

  async function handleSendMessage(prefill?: string) {
    const text = (prefill ?? inputText).trim();
    if (!text || loading) return;
    setError('');
    setLoading(true);
    if (!prefill) setInputText('');
    const userMsg: AssistMessage = { role: 'user', content: text };
    const nextMsgs    = [...messages, userMsg];
    const nextContext = [...conversationContext, text];
    setMessages(nextMsgs);
    setConversationContext(nextContext);
    await continueConversation(text, nextMsgs, nextContext);
    setLoading(false);
  }

  function buildHistory(msgs: AssistMessage[]): string {
    return msgs
      .filter((m) => m.role !== 'system')
      .map((m) => `${m.role === 'user' ? 'PATIENT' : 'YOU'}: ${m.content}`)
      .join('\n');
  }

  async function continueConversation(userMessage: string, currentMsgs: AssistMessage[], ctxSnap: string[]) {
    try {
      const data = await copilotContinueConversation({
        conversationHistory: buildHistory(currentMsgs),
        latestMessage: userMessage,
        language,
      });
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response || lang.greeting }]);
      if (data.should_auto_complete || data.conversation_complete) {
        setAutoCompleting(true);
        setTimeout(() => completeAssessment(ctxSnap), 1300);
      }
    } catch (e: unknown) {
      setError(getErrorMessage(e, 'Unable to continue conversation.'));
      setMessages((prev) => [...prev, { role: 'system', content: 'I could not process that. Please try again.' }]);
    }
  }

  async function completeAssessment(ctxSnap?: string[]) {
    setLoading(true);
    setError('');
    try {
      const fullText = (ctxSnap || conversationContext).join(' ');
      const triage   = await copilotProcessText(fullText, language);
      setResult(triage);
      setPhase('results');
    } catch (e: unknown) {
      setError(getErrorMessage(e, 'Unable to complete assessment.'));
      setAutoCompleting(false);
    } finally {
      setLoading(false);
    }
  }

  async function startRecording() {
    try {
      const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current   = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      recorder.onstop = () => {
        setAudioBlob(new Blob(audioChunksRef.current, { type: 'audio/webm' }));
        setRecordingState('recorded');
        stream.getTracks().forEach((t) => t.stop());
      };
      recorder.start();
      setRecordingState('recording');
      setRecordingTime(0);
      recordingTimerRef.current = setInterval(() => setRecordingTime((p) => p + 1), 1000);
    } catch {
      setError('Microphone access failed. Check browser permissions.');
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && recordingState === 'recording') {
      mediaRecorderRef.current.stop();
      if (recordingTimerRef.current) { clearInterval(recordingTimerRef.current); recordingTimerRef.current = null; }
    }
  }

  function cancelRecording() {
    if (recordingState === 'recording') stopRecording();
    setRecordingState('idle');
    setAudioBlob(null);
    setRecordingTime(0);
    audioChunksRef.current = [];
  }

  async function sendAudioMessage() {
    if (!audioBlob) return;
    setError('');
    setLoading(true);
    setRecordingState('processing');
    try {
      const triage = await copilotProcessAudio(audioBlob, language);
      if (triage.transcript) setMessages((prev) => [...prev, { role: 'user', content: triage.transcript || '', isAudio: true }]);
      setResult(triage);
      setPhase('results');
      setAudioBlob(null);
      setRecordingTime(0);
      setRecordingState('idle');
      audioChunksRef.current = [];
    } catch (e: unknown) {
      setError(getErrorMessage(e, 'Audio processing failed. Try typing instead.'));
      setRecordingState('recorded');
    } finally {
      setLoading(false);
    }
  }

  function resetAssist() {
    stopCurrentAudio();
    setPhase('language_select');
    setMessages([]);
    setConversationContext([]);
    setInputText('');
    setResult(null);
    setError('');
    setAutoCompleting(false);
    cancelRecording();
  }

  // ── Topbar ────────────────────────────────────────────────────────────────
  const Topbar = ({ showLang = false }: { showLang?: boolean }) => (
    <div className="hospital-topbar mb-5">
      <div className="hospital-brand">
        <span className="hospital-brand-mark">A+</span>
        <div>
          <div className="hospital-brand-title">Copilot Assist</div>
          <div className="hospital-brand-subtitle">
            {doctor.name}
            {doctor.specialty ? ` · ${doctor.specialty}` : ''}
            {showLang && ` · ${lang.nativeName}`}
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {sources && (
          <span className="hospital-chip hospital-chip-primary" style={{ display: 'none' }} />
        )}
        {phase !== 'language_select' && (
          <button className="hospital-btn hospital-btn-quiet" onClick={resetAssist} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <IcoReset /> Reset
          </button>
        )}
        <button className="hospital-btn hospital-btn-secondary" onClick={() => router.push('/doctor/scribe')} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <IcoBack /> Scribe
        </button>
      </div>
    </div>
  );

  // ── Error alert ────────────────────────────────────────────────────────────
  const errorAlert = error && (
    <div className="hospital-alert hospital-alert-danger" style={{ marginBottom: '0.85rem' }}>
      {error}
    </div>
  );

  // ── Sources bar ────────────────────────────────────────────────────────────
  const sourcesBar = sources && (
    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
      <span className="hospital-chip hospital-chip-primary">CHW {sources.chw}</span>
      <span className="hospital-chip hospital-chip-primary">Clinical {sources.clinical}</span>
      <span className="hospital-chip hospital-chip-neutral">Parsed {sources.parsed_guidelines}</span>
      <span className="hospital-chip hospital-chip-success" style={{ marginLeft: 'auto' }}>
        <span className="hospital-live-dot" /> KB Live
      </span>
    </div>
  );

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 1 — Language select
  // ══════════════════════════════════════════════════════════════════════════
  if (phase === 'language_select') return (
    <div className="hospital-page" style={{ padding: '2rem 1rem' }}>
      <div className="hospital-shell" style={{ maxWidth: '640px' }}>
        <Topbar />
        {sourcesBar}
        {errorAlert}

        <div className="hospital-card">
          <div style={{ marginBottom: '0.9rem' }}>
            <p style={{ fontSize: '0.73rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-soft)', fontWeight: 600, marginBottom: '0.2rem' }}>
              Triage Language
            </p>
            <p style={{ fontSize: '0.92rem', color: 'var(--text)', fontWeight: 700 }}>
              Select the patient's preferred language
            </p>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
              The assistant will greet, question, and respond in this language throughout the session.
            </p>
          </div>

          <div className="hospital-separator" />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.55rem', marginBottom: '1rem' }}>
            {ASSIST_LANGUAGE_ORDER.map((code) => {
              const item   = ASSIST_LANGUAGES[code];
              const active = code === language;
              return (
                <button
                  key={code}
                  onClick={() => setLanguage(code)}
                  className={`hospital-list-item${active ? ' active' : ''}`}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
                >
                  <span style={{ width: 4, minHeight: 36, borderRadius: 999, background: LANG_DOT[code], flexShrink: 0 }} />
                  <div style={{ flex: 1, textAlign: 'left' }}>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text)' }}>{item.nativeName}</div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-soft)' }}>{item.name}</div>
                  </div>
                  {active && <span style={{ color: 'var(--primary)', flexShrink: 0 }}><IcoCheck /></span>}
                </button>
              );
            })}
          </div>

          <button
            onClick={beginConversation}
            className="hospital-btn hospital-btn-primary"
            style={{ width: '100%', padding: '0.72rem', fontSize: '0.92rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
          >
            Begin Session in {lang.nativeName} <IcoArrow />
          </button>
        </div>
      </div>
    </div>
  );

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 2 — Conversation
  // ══════════════════════════════════════════════════════════════════════════
  if (phase === 'conversation') return (
    <div className="hospital-page" style={{ padding: '1.5rem 1rem 2rem' }}>
      <div className="hospital-shell" style={{ maxWidth: '680px' }}>
        <Topbar showLang />
        {errorAlert}

        {/* Chat window */}
        <div className="hospital-card" style={{ marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.73rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-soft)' }}>
              Conversation · {lang.nativeName}
            </span>
            {autoCompleting && (
              <span className="hospital-chip hospital-chip-primary">
                <span className="spinner" style={{ width: 10, height: 10, borderRadius: '50%', border: '2px solid #b5d4ef', borderTopColor: 'var(--primary)', display: 'inline-block' }} />
                Auto-completing
              </span>
            )}
          </div>

          <div className="hospital-chat">
            {messages.map((msg, idx) => {
              if (msg.role === 'system') return (
                <div key={idx} style={{ textAlign: 'center', margin: '0.35rem 0' }}>
                  <span className="hospital-chip hospital-chip-warning">{msg.content}</span>
                </div>
              );

              const isUser = msg.role === 'user';
              return (
                <div key={idx} style={{ display: 'flex', flexDirection: isUser ? 'row-reverse' : 'row', alignItems: 'flex-end', gap: '0.5rem', marginBottom: '0.55rem' }}>
                  {/* Avatar */}
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                    background: isUser ? '#374151' : 'var(--primary)',
                    color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: isUser ? '0.72rem' : undefined, fontWeight: 700,
                  }}>
                    {isUser ? doctor.name.charAt(0).toUpperCase() : <IcoBot />}
                  </div>

                  <div className={`hospital-chat-row ${msg.role}`} style={{ maxWidth: '78%' }}>
                    {msg.isAudio && (
                      <div style={{ fontSize: '0.72rem', opacity: 0.75, marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <IcoMic /> Audio transcript
                      </div>
                    )}
                    <span>{msg.content}</span>
                    {!isUser && (
                      <div style={{ marginTop: '0.4rem' }}>
                        <button
                          onClick={() => speakText(msg.content, language, () => setSpeaking(true), () => setSpeaking(false))}
                          className="hospital-btn hospital-btn-quiet"
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                        >
                          <IcoSpeaker /> {speaking ? 'Speaking…' : 'Listen'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && !autoCompleting && (
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.5rem' }}>
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--primary)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <IcoBot />
                </div>
                <div className="hospital-chat-row assistant" style={{ padding: '0.55rem 0.75rem' }}>
                  <div style={{ display: 'flex', gap: 5 }}>
                    {[0, 1, 2].map((i) => (
                      <span key={i} style={{
                        width: 7, height: 7, borderRadius: '50%', background: '#94a3b8',
                        animation: `bounce 1.2s ease-in-out ${i * 0.15}s infinite`,
                      }} />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Quick scenarios */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', marginBottom: '0.65rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-soft)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Try:</span>
          <button
            onClick={() => handleSendMessage('Severe chest pain started 30 minutes ago with sweating and shortness of breath.')}
            className="hospital-chip hospital-chip-neutral"
            style={{ cursor: 'pointer', border: '1px solid #d1dceb', background: '#eef3f9' }}
          >
            🫀 Chest Pain
          </button>
          <button
            onClick={() => handleSendMessage('Heavy bleeding after delivery with dizziness and weakness.')}
            className="hospital-chip hospital-chip-neutral"
            style={{ cursor: 'pointer', border: '1px solid #d1dceb', background: '#eef3f9' }}
          >
            🩺 Postpartum Emergency
          </button>
        </div>

        {/* Text input */}
        <div className="hospital-panel" style={{ marginBottom: '0.65rem', padding: '0.5rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
              placeholder={lang.placeholder}
              className="hospital-input"
              style={{ flex: 1, border: 'none', background: 'transparent', boxShadow: 'none', padding: '0.4rem 0.5rem' }}
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={loading || !inputText.trim()}
              className="hospital-btn hospital-btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', whiteSpace: 'nowrap' }}
            >
              {loading
                ? <span className="spinner" style={{ width: 14, height: 14, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', display: 'inline-block' }} />
                : <IcoSend />
              }
              {lang.sendLabel}
            </button>
          </div>
        </div>

        {/* Audio recording */}
        <div className="hospital-panel-muted" style={{ marginBottom: '0.65rem' }}>
          <p className="hospital-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <IcoMic /> Voice Input
          </p>

          {recordingState === 'idle' && (
            <button className="hospital-btn hospital-btn-secondary" onClick={startRecording} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#94a3b8', display: 'inline-block' }} />
              Start Recording
            </button>
          )}

          {recordingState === 'recording' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <div className="hospital-chip hospital-chip-danger" style={{ padding: '0.3rem 0.7rem' }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', background: 'var(--danger)',
                  display: 'inline-block', animation: 'hospital-pulse 1.5s ease-in-out infinite',
                  boxShadow: '0 0 0 0 rgba(191,47,64,0.45)',
                }} />
                {String(Math.floor(recordingTime / 60)).padStart(2, '0')}:{String(recordingTime % 60).padStart(2, '0')}
              </div>
              <button className="hospital-btn hospital-btn-secondary" onClick={stopRecording}>Stop</button>
              <button className="hospital-btn hospital-btn-quiet" onClick={cancelRecording}>Discard</button>
            </div>
          )}

          {recordingState === 'recorded' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <span className="hospital-chip hospital-chip-success">
                <IcoCheck /> Ready to send
              </span>
              <button className="hospital-btn hospital-btn-primary" onClick={sendAudioMessage}>Process Audio</button>
              <button className="hospital-btn hospital-btn-quiet" onClick={cancelRecording}>Discard</button>
            </div>
          )}

          {recordingState === 'processing' && (
            <span className="hospital-chip hospital-chip-primary">
              <span className="spinner" style={{ width: 10, height: 10, borderRadius: '50%', border: '2px solid #b5d4ef', borderTopColor: 'var(--primary)', display: 'inline-block' }} />
              Processing audio…
            </span>
          )}
        </div>

        {/* Complete assessment */}
        <button
          onClick={() => completeAssessment()}
          disabled={loading || conversationContext.length === 0}
          className="hospital-btn hospital-btn-primary"
          style={{ width: '100%', padding: '0.72rem', fontSize: '0.92rem' }}
        >
          {loading ? 'Analysing…' : lang.completeLabel}
        </button>
      </div>

      {/* Bounce keyframe */}
      <style>{`@keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }`}</style>
    </div>
  );

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 3 — Results
  // ══════════════════════════════════════════════════════════════════════════
  if (phase === 'results' && result) {
    return (
      <div className="hospital-page" style={{ padding: '2rem 1rem' }}>
        <div className="hospital-shell" style={{ maxWidth: '720px' }}>
          <Topbar />
          {errorAlert}

          {/* Risk hero */}
          <div className={`hospital-panel ${RISK_PANEL[result.risk_level]}`} style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
            <div>
              <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 700, opacity: 0.7, marginBottom: '0.2rem' }}>
                Triage Assessment Complete
              </p>
              <p style={{ fontSize: '1.55rem', fontWeight: 800, lineHeight: 1.1, marginBottom: '0.25rem' }}>
                {result.risk_level === 'high' ? '🔴' : result.risk_level === 'moderate' ? '🟡' : '🟢'} {RISK_LABEL[result.risk_level]}
              </p>
              <p style={{ fontSize: '0.84rem', fontWeight: 500, opacity: 0.8 }}>
                {lang.urgencyLabel}: {result.triage_recommendation.urgency_level}
              </p>
            </div>
            <span className={RISK_CHIP[result.risk_level]} style={{ flexShrink: 0, fontSize: '0.78rem' }}>
              {result.language?.toUpperCase() || language.toUpperCase()}
            </span>
          </div>

          {/* Summary */}
          <div className="hospital-card" style={{ marginBottom: '0.75rem' }}>
            <p className="hospital-panel-title">Summary of Findings</p>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.65, color: 'var(--text)' }}>
              {result.triage_recommendation.summary_of_findings}
            </p>
            <button
              onClick={() => speakText(result.triage_recommendation.summary_of_findings, language, () => setSpeaking(true), () => setSpeaking(false))}
              className="hospital-btn hospital-btn-quiet"
              style={{ marginTop: '0.65rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}
            >
              <IcoSpeaker /> {speaking ? 'Speaking…' : lang.speakSummaryLabel}
            </button>
          </div>

          {/* Symptoms */}
          {result.extracted_symptoms.length > 0 && (
            <div className="hospital-panel-muted" style={{ marginBottom: '0.75rem' }}>
              <p className="hospital-panel-title">{lang.symptomsLabel}</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
                {result.extracted_symptoms.map((s, i) => (
                  <span key={i} className="hospital-chip hospital-chip-neutral">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="hospital-card" style={{ marginBottom: '0.75rem' }}>
            <p className="hospital-panel-title">{lang.actionsLabel}</p>
            <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {result.triage_recommendation.recommended_actions_for_chw.map((action, idx) => (
                <li key={idx} style={{ display: 'flex', gap: '0.65rem', alignItems: 'flex-start' }}>
                  <span style={{
                    width: 22, height: 22, borderRadius: '50%', background: '#dbeafe',
                    color: 'var(--primary)', fontWeight: 800, fontSize: '0.72rem',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1,
                  }}>
                    {idx + 1}
                  </span>
                  <span style={{ fontSize: '0.88rem', lineHeight: 1.6, color: 'var(--text)' }}>{action}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* Evidence */}
          {result.evidence.length > 0 && (
            <div className="hospital-panel-muted" style={{ marginBottom: '0.75rem' }}>
              <p className="hospital-panel-title">Clinical Evidence Trail</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                {result.evidence.map((item, idx) => (
                  <div key={idx} className="hospital-panel" style={{ padding: '0.65rem 0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem', flexWrap: 'wrap' }}>
                      <span className="hospital-chip hospital-chip-neutral" style={{ fontSize: '0.66rem' }}>
                        {item.source_type.replace('_', ' ')}
                      </span>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)' }}>
                        {item.guideline_section}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.82rem', lineHeight: 1.55, color: 'var(--text-muted)' }}>
                      {item.source_excerpt}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CTAs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.6rem' }}>
            <button
              onClick={() => window.open('https://www.google.com/maps/search/hospital+near+me', '_blank')}
              className="hospital-btn hospital-btn-primary"
              style={{ padding: '0.72rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.45rem', fontSize: '0.9rem' }}
            >
              <IcoPin /> Find Nearest Hospital
            </button>
            <button
              onClick={resetAssist}
              className="hospital-btn hospital-btn-secondary"
              style={{ padding: '0.72rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.45rem', fontSize: '0.9rem' }}
            >
              <IcoReset /> {lang.restartLabel}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
