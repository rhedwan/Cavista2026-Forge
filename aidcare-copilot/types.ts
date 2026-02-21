// AidCare Copilot — Shared TypeScript types

export type DoctorRole = 'doctor' | 'admin';
export type BurnoutStatus = 'green' | 'amber' | 'red';
export type Language = 'en' | 'ha' | 'yo' | 'ig' | 'pcm';

export interface Doctor {
  doctor_id: string;
  name: string;
  specialty: string;
  ward: string;
  hospital?: string;
  role: DoctorRole;
}

export interface Shift {
  shift_id: string;
  started_at: string;
  ended_at?: string;
  ward: string;
  is_active: boolean;
}

export interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface Consultation {
  consultation_id: string;
  patient_ref: string;
  timestamp: string;
  transcript?: string;
  soap_note: SOAPNote;
  patient_summary: string;
  complexity_score: number; // 1-5
  flags: string[];
  language: Language;
}

export interface BurnoutScore {
  cognitive_load_score: number; // 0-100
  status: BurnoutStatus;
  breakdown: {
    volume: number;
    complexity: number;
    duration: number;
    consecutive: number;
  };
}

export interface BurnoutHistory {
  date: string;
  cls: number;
  status: BurnoutStatus;
}

export interface BurnoutDetail {
  doctor_id: string;
  doctor_name: string;
  current_shift?: {
    shift_id: string;
    start: string;
    patients_seen: number;
    hours_active: number;
  };
  cognitive_load_score: number;
  status: BurnoutStatus;
  score_breakdown: BurnoutScore['breakdown'];
  history_7_days: BurnoutHistory[];
  recommendation: string;
}

export interface CriticalPatient {
  patient_ref: string;
  summary: string;
  action_required: string;
  flags: string[];
}

export interface StablePatient {
  patient_ref: string;
  summary: string;
}

export interface HandoverReport {
  handover_id: string;
  generated_at: string;
  doctor_name: string;
  shift_summary: {
    start: string;
    end: string;
    patients_seen: number;
    avg_complexity: number;
  };
  critical_patients: CriticalPatient[];
  stable_patients: StablePatient[];
  discharged_patients: StablePatient[];
  handover_notes?: string;
  plain_text_report: string;
}

export interface DoctorDashboardCard {
  doctor_id: string;
  name: string;
  specialty: string;
  ward: string;
  cls: number;
  status: BurnoutStatus;
  patients_seen: number;
  hours_active: number;
}

export interface AdminDashboard {
  generated_at: string;
  team_stats: {
    total_active: number;
    red_count: number;
    amber_count: number;
    green_count: number;
    avg_cls: number;
    total_patients_today: number;
  };
  doctors: DoctorDashboardCard[];
  red_zone_alerts: {
    doctor_id: string;
    name: string;
    cls: number;
    message: string;
  }[];
}

export interface ScribeResult {
  transcript: string;
  soap_note: SOAPNote;
  patient_summary: string;
  complexity_score: number;
  flags: string[];
}
