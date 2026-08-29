/**
 * API-facing mirrors of backend/app/schemas/contracts.py.
 *
 * Decimal values are strings over JSON to preserve monetary precision.
 * Timestamps are ISO-8601 strings with an explicit UTC offset.
 */

export type FraudLabel = "legitimate" | "fraudulent" | "unknown";

export type PaymentMethodType =
  | "card"
  | "bank_transfer"
  | "wallet"
  | "upi"
  | "cash"
  | "other";

export type PaymentStatus =
  | "pending"
  | "authorized"
  | "captured"
  | "failed"
  | "cancelled"
  | "refunded"
  | "disputed";

export type IncidentSeverity = "low" | "medium" | "high" | "critical";

export type IncidentStatus =
  | "detected"
  | "investigating"
  | "verified"
  | "dismissed"
  | "resolved";

export type EvidenceCategory =
  | "merchant_baseline"
  | "transaction_pattern"
  | "temporal"
  | "payment_method"
  | "geography"
  | "device"
  | "customer_pattern"
  | "external_signal"
  | "other";

export type InvestigationStatus =
  | "queued"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled";

export type VerificationResult =
  | "unverified"
  | "confirmed_fraud_spike"
  | "false_positive"
  | "inconclusive";

export type AuditEventType =
  | "detection"
  | "investigation"
  | "verification"
  | "response"
  | "data_access"
  | "system";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface CoarseGeography {
  country_code?: string | null;
  region_code?: string | null;
}

export interface AnalysisWindow {
  start_at: string;
  end_at: string;
}

export interface PaymentEvent {
  event_id: string;
  merchant_id: string;
  occurred_at: string;
  amount: string;
  currency: string;
  payment_method: PaymentMethodType;
  payment_status: PaymentStatus;
  customer_reference: string;
  device_reference: string;
  geography?: CoarseGeography | null;
  fraud_label: FraudLabel;
  metadata: Record<string, JsonValue>;
}

export interface FraudSpikeIncident {
  incident_id: string;
  merchant_id: string;
  detected_at: string;
  analysis_window: AnalysisWindow;
  baseline_fraud_rate: string;
  observed_fraud_rate: string;
  deviation: string;
  affected_transaction_count: number;
  severity: IncidentSeverity;
  status: IncidentStatus;
  detector_version: string;
  confidence?: string | null;
}

export interface EvidenceItem {
  evidence_id: string;
  incident_id: string;
  category: EvidenceCategory;
  metric: string;
  value: JsonValue;
  baseline_value?: JsonValue | null;
  supporting_event_ids: string[];
  window?: AnalysisWindow | null;
  confidence?: string | null;
}

export interface Investigation {
  investigation_id: string;
  incident_id: string;
  status: InvestigationStatus;
  started_at?: string | null;
  ended_at?: string | null;
  hypotheses: string[];
  evidence_ids: string[];
  verification_result?: VerificationResult | null;
  confidence?: string | null;
  explanation?: string | null;
  recommended_defensive_response?: string | null;
}

export interface EvaluationResult {
  evaluation_id: string;
  dataset_version: string;
  held_out_test_set_id: string;
  detector_version: string;
  true_positives?: number | null;
  true_negatives?: number | null;
  false_positives?: number | null;
  false_negatives?: number | null;
  precision?: string | null;
  recall?: string | null;
  f1?: string | null;
  false_positive_count?: number | null;
  false_positive_cost?: string | null;
  evaluated_at?: string | null;
}

export interface AuditEvent {
  event_id: string;
  occurred_at: string;
  event_type: AuditEventType;
  actor?: string | null;
  source?: string | null;
  incident_id?: string | null;
  investigation_id?: string | null;
  action: string;
  details: Record<string, JsonValue>;
}