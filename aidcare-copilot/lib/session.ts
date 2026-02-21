'use client';
// Session management — localStorage-based for hackathon MVP

const DOCTOR_KEY = 'copilot_doctor';
const SHIFT_KEY = 'copilot_shift';

export interface SessionDoctor {
  doctor_id: string;
  name: string;
  specialty: string;
  ward: string;
  role: string;
}

export interface SessionShift {
  shift_id: string;
  started_at: string;
  ward: string;
}

export function getSessionDoctor(): SessionDoctor | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(DOCTOR_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSessionDoctor(doctor: SessionDoctor) {
  localStorage.setItem(DOCTOR_KEY, JSON.stringify(doctor));
}

export function clearSessionDoctor() {
  localStorage.removeItem(DOCTOR_KEY);
  localStorage.removeItem(SHIFT_KEY);
}

export function getSessionShift(): SessionShift | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(SHIFT_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSessionShift(shift: SessionShift) {
  localStorage.setItem(SHIFT_KEY, JSON.stringify(shift));
}

export function clearSessionShift() {
  localStorage.removeItem(SHIFT_KEY);
}

export function getShiftDuration(startedAt: string): string {
  const start = new Date(startedAt);
  const now = new Date();
  const diffMs = now.getTime() - start.getTime();
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  return `${hours}h ${mins}m`;
}
