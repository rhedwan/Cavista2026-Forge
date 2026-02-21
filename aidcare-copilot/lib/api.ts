'use client';

import { AuthTokenResponse, AuthUser, Patient, PatientDetail, ActionItem, ScribeResult, HandoverReport, Language } from '../types';
import { getToken, clearSession } from './session';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...(init?.headers as Record<string, string> || {}),
  };
  const res = await fetch(`${API}${path}`, { ...init, headers });
  if (res.status === 401) {
    clearSession();
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new ApiError(401, 'Session expired');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let detail = text;
    try { detail = JSON.parse(text).detail || text; } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

async function apiForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });
  if (res.status === 401) {
    clearSession();
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new ApiError(401, 'Session expired');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let detail = text;
    try { detail = JSON.parse(text).detail || text; } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export function getError(err: unknown, fallback = 'Something went wrong.'): string {
  if (err instanceof ApiError) return err.detail || fallback;
  if (err instanceof Error) return err.message || fallback;
  return fallback;
}

// ── Auth ──
export const login = (email: string, password: string) =>
  api<AuthTokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });

export const register = (params: { email: string; password: string; full_name: string; specialty?: string; role?: string }) =>
  api<AuthTokenResponse>('/auth/register', { method: 'POST', body: JSON.stringify(params) });

export const getMe = () => api<AuthUser>('/auth/me');

// ── Shifts ──
export const startShift = (wardUuid?: string) =>
  api<{ shift_id: string; started_at: string; ward_id: string | null }>('/doctor/shifts/start/', {
    method: 'POST', body: JSON.stringify({ ward_uuid: wardUuid || null }),
  });

export const endShift = (shiftUuid: string) =>
  api<{ ended_at: string; final_cls: number; status: string }>('/doctor/shifts/end/', {
    method: 'POST', body: JSON.stringify({ shift_uuid: shiftUuid }),
  });

export const getActiveShift = () =>
  api<{ shift: { shift_id: string; started_at: string; ward_id: string | null; ward_name: string | null } | null }>('/doctor/shifts/active');

// ── Scribe ──
export function transcribeAndScribe(audioBlob: Blob, patientUuid: string, patientRef: string, language: Language): Promise<ScribeResult> {
  const fd = new FormData();
  fd.append('audio_file', audioBlob, 'recording.webm');
  fd.append('patient_uuid', patientUuid);
  fd.append('patient_ref', patientRef);
  fd.append('language', language);
  return apiForm('/doctor/scribe/', fd);
}

// ── Patients ──
export const getPatients = (wardUuid?: string) =>
  api<{ total: number; patients: { critical: Patient[]; stable: Patient[]; discharged: Patient[] } }>(
    `/patients/${wardUuid ? `?ward_uuid=${wardUuid}` : ''}`
  );

export const getPatientDetail = (uuid: string) => api<PatientDetail>(`/patients/${uuid}`);

export const getPatientAISummary = (uuid: string) =>
  api<{ chronic_conditions: { condition: string; details: string }[]; flagged_patterns: string[]; summary: string }>(
    `/patients/${uuid}/ai-summary`
  );

export const createPatient = (params: Record<string, unknown>) =>
  api<Patient>('/patients/', { method: 'POST', body: JSON.stringify(params) });

export const createActionItem = (patientUuid: string, params: { description: string; priority?: string }) =>
  api<ActionItem>(`/patients/${patientUuid}/action-items`, { method: 'POST', body: JSON.stringify(params) });

export const completeActionItem = (itemUuid: string) =>
  api<ActionItem>(`/patients/action-items/${itemUuid}/complete`, { method: 'PATCH' });

// ── Handover ──
export const generateHandover = (shiftUuid: string, wardUuid?: string, notes?: string) =>
  api<HandoverReport>('/doctor/handover/', {
    method: 'POST',
    body: JSON.stringify({ shift_uuid: shiftUuid, ward_uuid: wardUuid || null, handover_notes: notes || '' }),
  });

export const getShiftConsultations = (shiftUuid: string) =>
  api<{ consultations_count: number; consultations: import('../types').Consultation[] }>(
    `/doctor/handover/consultations?shift_uuid=${shiftUuid}`
  );

// ── Triage ──
export const triageContinue = (params: { conversation_history: string; patient_message: string; staff_notes?: string; language: string }) =>
  api<{ response: string; language: string; conversation_complete: boolean; should_auto_complete: boolean }>(
    '/triage/conversation/continue', { method: 'POST', body: JSON.stringify(params) }
  );

export const triageProcessText = (transcript: string, language: string, staffNotes?: string) =>
  api<{ language: string; extracted_symptoms: string[]; triage_recommendation: Record<string, unknown>; risk_level: string }>(
    '/triage/process_text', { method: 'POST', body: JSON.stringify({ transcript_text: transcript, staff_notes: staffNotes || '', language }) }
  );

export function triageProcessAudio(audioBlob: Blob, language: string, staffNotes?: string) {
  const fd = new FormData();
  fd.append('audio_file', audioBlob, 'triage.webm');
  fd.append('language', language);
  fd.append('staff_notes', staffNotes || '');
  return apiForm<Record<string, unknown>>('/triage/process_audio', fd);
}

export async function triageTTS(text: string, language: string): Promise<Blob> {
  const res = await fetch(`${API}/triage/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ text, language }),
  });
  if (!res.ok) throw new ApiError(res.status, 'TTS failed');
  return res.blob();
}

export const triageSave = (patientUuid: string, result: Record<string, unknown>) =>
  api<{ status: string }>(`/triage/save/${patientUuid}`, { method: 'POST', body: JSON.stringify({ triage_result: result }) });

// ── Burnout ──
export const getMyBurnout = () => api<Record<string, unknown>>('/doctor/burnout/me');

// ── Admin ──
export const getAdminDashboard = (wardUuid?: string) =>
  api<Record<string, unknown>>(`/admin/dashboard/${wardUuid ? `?ward_uuid=${wardUuid}` : ''}`);
