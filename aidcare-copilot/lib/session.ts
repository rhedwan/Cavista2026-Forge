'use client';

import { AuthUser } from '../types';

const TOKEN_KEY = 'aidcare_token';
const USER_KEY = 'aidcare_user';
const SHIFT_KEY = 'copilot_shift';

export interface SessionShift {
  shift_id: string;
  started_at: string;
  ward_id: string | null;
  ward_name: string | null;
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getSessionUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSessionUser(user: AuthUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
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

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function getShiftDuration(startedAt: string): string {
  const start = new Date(startedAt);
  const now = new Date();
  const diffMs = now.getTime() - start.getTime();
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  return `${hours}h ${mins}m`;
}
