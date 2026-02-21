export type DoctorRole = 'super_admin' | 'org_admin' | 'hospital_admin' | 'doctor' | 'admin';
export type BurnoutStatus = 'green' | 'amber' | 'red';
export type Language = 'en' | 'ha' | 'yo' | 'ig' | 'pcm';
export type PatientStatus = 'critical' | 'stable' | 'discharged';

export interface AuthUser {
  doctor_id: string;
  email: string;
  name: string;
  specialty: string;
  role: DoctorRole;
  hospital_id: string | null;
  hospital_name: string | null;
  ward_id: string | null;
  ward_name: string | null;
  org_id: string | null;
  org_name: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
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
  patient_id: string | null;
  timestamp: string;
  transcript?: string;
  pidgin_detected?: boolean;
  soap_note: SOAPNote;
  patient_summary: string;
  complexity_score: number;
  flags: string[];
  medication_changes?: MedicationChange[];
  language: Language;
  doctor_name?: string;
}

export interface MedicationChange {
  action: 'started' | 'stopped' | 'continued';
  drug: string;
  dose?: string;
  reason?: string;
  consultation_time?: string;
  doctor_name?: string;
}

export interface ScribeResult {
  consultation_id: string | null;
  patient_ref: string;
  transcript: string;
  pidgin_detected: boolean;
  soap_note: SOAPNote;
  patient_summary: string;
  complexity_score: number;
  flags: string[];
  medication_changes: MedicationChange[];
  burnout_score: { cls: number; status: BurnoutStatus } | null;
}

export interface Patient {
  patient_id: string;
  full_name: string;
  age: number | null;
  gender: string | null;
  bed_number: string | null;
  status: PatientStatus;
  primary_diagnosis: string | null;
  admission_date: string | null;
  discharge_date: string | null;
  vitals: Record<string, string | number> | null;
  allergies: string[] | null;
  active_medications: { name: string; dose: string }[] | null;
  medical_history: { condition: string; date?: string; notes?: string }[] | null;
  triage_result: Record<string, unknown> | null;
  ward_id: string | null;
  ward_name: string | null;
  attending_doctor_id: string | null;
  attending_doctor_name: string | null;
}

export interface PatientDetail extends Patient {
  consultations: Consultation[];
  action_items: ActionItem[];
  medication_changes: MedicationChange[];
}

export interface ActionItem {
  item_id: string;
  description: string;
  priority: 'high' | 'normal' | 'low';
  due_time: string | null;
  completed: boolean;
  completed_at: string | null;
  created_at: string;
  created_by: string | null;
}

export interface HandoverReport {
  handover_id: string;
  generated_at: string;
  doctor_name: string;
  ward_name: string | null;
  shift_summary: {
    start: string;
    end: string;
    patients_seen: number;
    avg_complexity: number;
  };
  critical_patients: {
    patient_ref: string;
    patient_id: string | null;
    summary: string;
    action_required: string;
    flags: string[];
    medication_changes: MedicationChange[];
    soap_assessment?: string;
    complexity_score?: number;
    doctor_name?: string;
    timestamp?: string;
  }[];
  stable_patients: {
    patient_ref: string;
    patient_id: string | null;
    summary: string;
    medication_changes?: MedicationChange[];
    doctor_name?: string;
    timestamp?: string;
  }[];
  discharged_patients: {
    patient_ref: string;
    patient_id: string | null;
    summary: string;
  }[];
  handover_notes?: string;
  plain_text_report: string;
}
