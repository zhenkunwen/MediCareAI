/** 患者端 API 服务层 */

import { API_BASE } from './client';

import { authHeaders } from './client';

/** 后端 HealthProfileResponse 的实际返回结构 */
export interface BackendProfile {
  user_id: string;
  date_of_birth: string | null;
  gender: string | null;
  blood_type: string | null;
  height: number | null;
  weight: number | null;
  allergies: string[];
  chronic_diseases: string[];
  medications: Array<{
    name: string;
    dosage: string;
    frequency: string;
    start_date: string;
    end_date?: string | null;
  }>;
  created_at: string;
  updated_at: string;
}

export interface PatientProfile {
  id: string;
  name: string;
  email: string;
  phone?: string;
  date_of_birth?: string;
  gender?: string;
  blood_type?: string;
  height?: number;
  weight?: number;
  allergies?: string[];
  chronic_diseases?: string[];
  medications?: Array<{
    name: string;
    dosage: string;
    frequency: string;
    start_date?: string;
  }>;
}

export interface MedicalCase {
  id: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
  diagnosis?: string;
}

export interface CarePlan {
  id: string;
  title: string;
  goals: string[];
  status: string;
  tasks: Array<{
    id: string;
    description: string;
    due_date?: string;
    status: string;
    order?: number;
  }>;
  start_date: string;
  end_date?: string;
}

export async function getProfile(): Promise<BackendProfile> {
  const res = await fetch(`${API_BASE}/patient/profile`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch profile');
  return res.json();
}

export async function updateProfile(data: Partial<PatientProfile>): Promise<BackendProfile> {
  const res = await fetch(`${API_BASE}/patient/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    let detail = `保存失败 (${res.status})`;
    try { const j = JSON.parse(body); detail = j.detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export async function listCases(): Promise<MedicalCase[]> {
  const res = await fetch(`${API_BASE}/patient/cases`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch cases');
  return res.json();
}

export async function listCarePlans(): Promise<CarePlan[]> {
  const res = await fetch(`${API_BASE}/patient/care-plans?include_tasks=true&size=50`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch care plans');
  const data = await res.json();
  // Backend returns paginated response { items: [...], total, page, size, pages }
  return (data?.items ?? data) as CarePlan[];
}

export async function ackTask(planId: string, taskId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/patient/care-plans/${planId}/tasks/${taskId}/complete`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Failed to complete task');
}

// ── Medication Reminders ──────────────────────────────────────────────

export interface MedicationReminder {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  time_slots: string[];
  start_date: string;
  end_date?: string;
  status: string;
  note?: string;
  today_records?: Array<{ id: string; scheduled_time: string; status: string; taken_at?: string }>;
  created_at: string;
}

export interface TodayMedicationItem {
  reminder_id: string;
  record_id: string;
  name: string;
  dosage: string;
  scheduled_time: string;
  taken_at?: string;
  status: string;
}

export interface TodayMedicationResponse {
  items: TodayMedicationItem[];
  taken_count: number;
  pending_count: number;
  total_count: number;
}

export async function createMedication(data: {
  name: string; dosage: string; frequency: string; time_slots?: string[];
  lead_minutes?: number; remind_enabled?: boolean;
}): Promise<MedicationReminder> {
  const res = await fetch(`${API_BASE}/patient/medications`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create medication');
  return res.json();
}

export async function listMedications(): Promise<MedicationReminder[]> {
  const res = await fetch(`${API_BASE}/patient/medications`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch medications');
  return res.json();
}

export async function getTodayMedications(): Promise<TodayMedicationResponse> {
  const res = await fetch(`${API_BASE}/patient/medications/today`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch today medications');
  return res.json();
}

export async function takeMedication(medicationId: string): Promise<{ id: string; status: string; taken_at?: string }> {
  const res = await fetch(`${API_BASE}/patient/medications/${medicationId}/take`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Failed to take medication');
  return res.json();
}

export async function deleteMedication(medicationId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/patient/medications/${medicationId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Failed to delete medication');
}
