export type HealthResponse = {
  status: "ok";
  service: string;
};

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => apiFetch<HealthResponse>("/api/health"),
  summary: () => apiFetch<DashboardSummary>("/api/dashboard/summary"),
  metrics: () => apiFetch<DashboardSummary>("/api/dashboard/metrics"),
  merchants: () => apiFetch<string[]>("/api/merchants"),
  merchantDetail: (merchantId: string) => apiFetch<MerchantDetail>(`/api/merchants/${merchantId}`),
  incidents: () => apiFetch<IncidentRecord[]>("/api/incidents"),
  incidentDetail: (incidentId: string) => apiFetch<IncidentRecord>(`/api/incidents/${incidentId}`),
  investigation: (incidentId: string) => apiFetch<InvestigationRecord>(`/api/incidents/${incidentId}/investigation`),
  verification: (incidentId: string) => apiFetch<VerificationRecord>(`/api/incidents/${incidentId}/verification`),
  audit: (incidentId: string) => apiFetch<AuditEventRecord[]>(`/api/incidents/${incidentId}/audit`),
  evaluation: () => apiFetch<EvaluationRecord>("/api/evaluation"),
  razorpay: () => apiFetch<RazorpayStatus>("/api/demo/razorpay"),
  demoSeed: () => apiFetch<{ status: string; total_events: number; merchants: string[] }>("/api/demo/seed", {
    method: "POST",
  }),
  incidentAction: (incidentId: string, action: string, notes?: string) => {
    const params = new URLSearchParams({ action });
    if (notes) params.set("notes", notes);
    return apiFetch<IncidentRecord>(`/api/incidents/${incidentId}/action?${params.toString()}`, {
      method: "POST",
    });
  },
};

export type DashboardSummary = {
  total_transactions: number;
  fraud_rate: number;
  active_incidents: number;
  severity_breakdown: Record<"critical" | "high" | "medium" | "low", number>;
  merchant_risk_ranking: Array<{
    merchant_id: string;
    total_transactions: number;
    fraudulent_transactions: number;
    fraud_rate: number;
  }>;
  false_positive_cost_estimate: string;
};

export type MerchantDetail = {
  merchant_id: string;
  total_transactions: number;
  fraudulent_transactions: number;
  risk_score: number;
  baseline_vs_current: {
    baseline_fraud_rate: string;
    current_fraud_rate: string;
  };
};

export type IncidentRecord = {
  incident_id: string;
  merchant_id: string;
  detected_at: string;
  analysis_window: {
    start_at: string;
    end_at: string;
  };
  baseline_fraud_rate: string;
  observed_fraud_rate: string;
  deviation: string;
  affected_transaction_count: number;
  severity: "critical" | "high" | "medium" | "low";
  status: string;
  detector_version: string;
  confidence: string | null;
};

export type InvestigationRecord = {
  investigation_id: string;
  incident_id: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  hypotheses: string[];
  evidence_ids: string[];
  verification_result: string | null;
  confidence: string | null;
  explanation: string | null;
  recommended_defensive_response: string | null;
};

export type VerificationRecord = {
  verification_status: string;
  confidence: string;
  supported_claims: string[];
  unsupported_claims: string[];
  evidence_references: string[];
  ai_generated_conclusion: string;
  system_verified_evidence: boolean;
};

export type AuditEventRecord = {
  event_id: string;
  occurred_at: string;
  event_type: string;
  action: string;
  details: Record<string, unknown>;
  source: string | null;
};

export type EvaluationRecord = {
  test_set_size: number;
  tp: number;
  tn: number;
  fp: number;
  fn: number;
  precision: string;
  recall: string;
  f1: string;
  confusion_matrix: number[][];
  false_positive_cost: string;
};

export type RazorpayStatus = {
  enabled: boolean;
  mode: string;
  message: string;
};