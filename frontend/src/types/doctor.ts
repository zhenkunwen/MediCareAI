// DoctorAgent module type definitions

export interface PossibleDisease {
  disease: string;
  confidence: number;
}

export interface PreDiagnosisDetail {
  possible_diseases: PossibleDisease[];
  suggested_tests: string[];
  urgency: string;
}

export interface VitalSigns {
  temperature?: number;
  heart_rate?: number;
  respiratory_rate?: number;
  blood_pressure_systolic?: number;
  blood_pressure_diastolic?: number;
  oxygen_saturation?: number;
  weight?: number;
  height?: number;
}

export interface PendingConsultationItem {
  consultation_id: string;
  case_id: string;
  patient_id: string;
  patient_name: string;
  chief_complaint: string;
  pre_diagnosis: PreDiagnosisDetail;
  vitals: VitalSigns;
  allergies: string[];
  status: string;
  created_at: string;
}

export interface PendingConsultationListResponse {
  consultations: PendingConsultationItem[];
}

export interface MedicationItem {
  name: string;
  dosage: string;
  frequency: string;
  days: number;
  route: string;
}

export interface TreatmentPlan {
  medications: MedicationItem[];
  advice: string[];
  follow_up?: string;
}

export interface FinalizeDiagnosisRequest {
  consultation_id: string;
  final_diagnosis: string;
  icd11_code?: string;
  treatment_plan?: TreatmentPlan;
  doctor_notes?: string;
  physical_exam?: VitalSigns;
  rejected_suggestions?: string[];
}

export interface FinalizeDiagnosisResponse {
  status: string;
  consultation_id: string;
}

export interface ConsultationHistoryItem {
  consultation_id: string;
  case_id: string;
  doctor_id: string;
  final_diagnosis: string;
  icd11_code?: string;
  treatment_plan?: TreatmentPlan;
  doctor_notes?: string;
  created_at: string;
}

export interface ConsultationHistoryListResponse {
  records: ConsultationHistoryItem[];
}
