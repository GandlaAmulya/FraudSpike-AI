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

export type IngestionInputRow = Record<string, unknown>;
export type IngestionResult = {
  accepted: number;
  rejected: number;
  "duplicate/skipped": number;
  incidents_created: number;
  records_received: number;
  records_accepted: number;
  records_rejected: number;
  duplicates: number;
  merchants_detected: number;
  processing_time_ms: number;
  risk_summary: {
    records_processed: number;
    high_risk: number;
    medium_risk: number;
    low_risk: number;
    fraud_rate: number;
    average_risk: number;
    merchants_affected: number;
    top_risk_merchants: Array<{ merchant_id: string; average_risk: number }>;
  };
  rejected_rows: Array<{
    index: number;
    error: string;
    payload: Record<string, unknown>;
  }>;
};

export type RiskScoreInput = Record<string, unknown>;
export type RiskScoreResult = {
  risk_score: number;
  risk_level: string;
  decision: string;
  decision_path: string;
  reasons: string[];
  confidence: number;
  evidence: Record<string, unknown>;
};

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
  ingest: (rows: IngestionInputRow[]) => apiFetch<IngestionResult>("/api/ingest", {
    method: "POST",
    body: JSON.stringify({ rows }),
  }),
  syntheticStream: (scenario: string) => apiFetch<IngestionResult>("/api/stream/synthetic", {
    method: "POST",
    body: JSON.stringify({ scenario }),
  }),
  riskScore: (event: RiskScoreInput) => apiFetch<RiskScoreResult>("/api/risk/score", {
    method: "POST",
    body: JSON.stringify(event),
  }),
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

export function percent(value: number | string | undefined, digits = 2): string {
  if (value === undefined || value === null || value === "") return "—";
  const asNumber = typeof value === "string" ? Number(value) : Number(value);
  if (Number.isNaN(asNumber)) return String(value);
  return `${(asNumber * 100).toFixed(digits)}%`;
}

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
  provider?: string | null;
  risk_level?: string | null;
  findings?: string[];
  evidence_references?: string[];
  reasoning_summary?: string | null;
  recommended_action?: string | null;
  limitations?: string[];
  ml_assessment?: {
    model?: string | null;
    model_version?: string | null;
    available?: boolean | null;
    anomaly_score?: number | null;
    assessment?: string | null;
    features_used?: string[];
    evidence_references?: string[];
    reasoning_summary?: string | null;
    limitations?: string[];
  } | null;
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