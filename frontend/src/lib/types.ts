export type Severity = "critical" | "high" | "medium" | "low";

export interface DashboardSummary {
  total_transactions: number;
  fraud_rate: number;
  active_incidents: number;
  severity_breakdown: Record<Severity, number>;
  merchant_risk_ranking: Array<{
    merchant_id: string;
    total_transactions: number;
    fraudulent_transactions: number;
    fraud_rate: number;
  }>;
  false_positive_cost_estimate: string;
}

export interface IncidentRecord {
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
  severity: Severity;
  status: string;
  detector_version: string;
  confidence: string | null;
}

export interface InvestigationRecord {
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
}
