// Enhanced Doctor API functions for DoctorAgent module.

import type {
    PendingConsultationListResponse,
    FinalizeDiagnosisRequest,
    FinalizeDiagnosisResponse,
    ConsultationHistoryListResponse,
} from '../types/doctor';
import { API_BASE, authHeaders, jsonHeaders } from './client';

export async function fetchPendingConsultations(): Promise<PendingConsultationListResponse> {
    const res = await fetch(`${API_BASE}/doctor/consultations/pending`, {
        headers: authHeaders(),
    });
    if (!res.ok) throw new Error('获取待决策列表失败');
    return res.json();
}

export async function finalizeConsultation(
    data: FinalizeDiagnosisRequest,
): Promise<FinalizeDiagnosisResponse> {
    const res = await fetch(`${API_BASE}/doctor/consultations/finalize`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '提交失败' }));
        throw new Error(err.detail || '提交失败');
    }
    return res.json();
}

export async function fetchDecisionHistory(
    limit: number = 20,
): Promise<ConsultationHistoryListResponse> {
    const res = await fetch(`${API_BASE}/doctor/decisions?limit=${limit}`, {
        headers: authHeaders(),
    });
    if (!res.ok) throw new Error('获取决策历史失败');
    return res.json();
}
