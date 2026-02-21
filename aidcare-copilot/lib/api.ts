'use client';
// AidCare Copilot — API client

import {
  Doctor,
  Shift,
  Consultation,
  SOAPNote,
  ScribeResult,
  HandoverReport,
  BurnoutDetail,
  AdminDashboard,
  Language,
} from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${err}`);
  }
  return res.json();
}

// ─── Doctor ───────────────────────────────────────────────────────────────────

export async function getDoctors(): Promise<{ doctors: Doctor[] }> {
  return apiFetch('/doctor/list/');
}

export async function getDoctorProfile(doctorId: string): Promise<Doctor> {
  return apiFetch(`/doctor/profile/${doctorId}`);
}

// ─── Shifts ───────────────────────────────────────────────────────────────────

export async function startShift(doctorUuid: string, ward: string): Promise<{ shift_id: string; started_at: string }> {
  return apiFetch('/doctor/shifts/start/', {
    method: 'POST',
    body: JSON.stringify({ doctor_uuid: doctorUuid, ward }),
  });
}

export async function endShift(doctorUuid: string, shiftUuid: string): Promise<{ ended_at: string; final_cls: number; status: string }> {
  return apiFetch('/doctor/shifts/end/', {
    method: 'POST',
    body: JSON.stringify({ doctor_uuid: doctorUuid, shift_uuid: shiftUuid }),
  });
}

// ─── Scribe ───────────────────────────────────────────────────────────────────

export async function transcribeAndScribe(
  audioBlob: Blob,
  doctorUuid: string,
  patientRef: string,
  language: Language
): Promise<ScribeResult> {
  const formData = new FormData();
  formData.append('audio_file', audioBlob, 'recording.webm');
  formData.append('doctor_uuid', doctorUuid);
  formData.append('patient_ref', patientRef);
  formData.append('language', language);

  const res = await fetch(`${API_BASE}/doctor/scribe/`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(`Scribe API ${res.status}: ${err}`);
  }
  return res.json();
}

// ─── Consultations ────────────────────────────────────────────────────────────

export async function saveConsultation(params: {
  doctorUuid: string;
  shiftUuid: string;
  patientRef: string;
  transcript: string;
  soapNote: SOAPNote;
  patientSummary: string;
  complexityScore: number;
  flags: string[];
  language: Language;
}): Promise<{ consultation_id: string; saved_at: string; burnout_score: { cls: number; status: string } }> {
  return apiFetch('/doctor/consultations/', {
    method: 'POST',
    body: JSON.stringify({
      doctor_uuid: params.doctorUuid,
      shift_uuid: params.shiftUuid,
      patient_ref: params.patientRef,
      transcript: params.transcript,
      soap_note: params.soapNote,
      patient_summary: params.patientSummary,
      complexity_score: params.complexityScore,
      flags: params.flags,
      language: params.language,
    }),
  });
}

export async function getShiftConsultations(
  doctorUuid: string,
  shiftUuid: string
): Promise<{ consultations_count: number; consultations: Consultation[] }> {
  return apiFetch(`/doctor/consultations/${doctorUuid}?shift_uuid=${shiftUuid}`);
}

// ─── Handover ─────────────────────────────────────────────────────────────────

export async function generateHandover(
  doctorUuid: string,
  shiftUuid: string,
  handoverNotes?: string
): Promise<HandoverReport> {
  return apiFetch('/doctor/handover/', {
    method: 'POST',
    body: JSON.stringify({
      doctor_uuid: doctorUuid,
      shift_uuid: shiftUuid,
      handover_notes: handoverNotes || '',
    }),
  });
}

// ─── Burnout ──────────────────────────────────────────────────────────────────

export async function getBurnoutScore(doctorUuid: string): Promise<BurnoutDetail> {
  return apiFetch(`/doctor/burnout/${doctorUuid}`);
}

// ─── Admin ────────────────────────────────────────────────────────────────────

export async function getAdminDashboard(): Promise<AdminDashboard> {
  return apiFetch('/admin/dashboard/');
}

export async function getDoctorDetail(doctorUuid: string) {
  return apiFetch(`/admin/doctor/${doctorUuid}/detail`);
}
