import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "./lib/api";
import type {
  AuditEventRecord,
  DashboardSummary,
  EvaluationRecord,
  IncidentRecord,
  InvestigationRecord,
  MerchantDetail,
  RazorpayStatus,
  VerificationRecord,
} from "./lib/api";

type View = "dashboard" | "merchants" | "incidents" | "investigation" | "evaluation" | "audit" | "system";

const severityColors: Record<string, string> = {
  critical: "#ff6b6b",
  high: "#ff9f43",
  medium: "#feca57",
  low: "#54c6eb",
};

const statusTone: Record<string, string> = {
  detected: "#fbbf24",
  investigating: "#60a5fa",
  verified: "#34d399",
  dismissed: "#f87171",
  resolved: "#a78bfa",
};

const navItems: Array<{ id: View; label: string; icon: string }> = [
  { id: "dashboard", label: "Dashboard", icon: "▣" },
  { id: "merchants", label: "Merchants", icon: "◫" },
  { id: "incidents", label: "Incidents", icon: "◌" },
  { id: "investigation", label: "Investigations", icon: "◎" },
  { id: "evaluation", label: "Evaluation", icon: "▤" },
  { id: "audit", label: "Audit Trail", icon: "◍" },
  { id: "system", label: "System Status", icon: "◐" },
];

function formatMetricValue(value: number | string | undefined, digits = 2) {
  if (value === undefined || value === null || value === "") return "—";
  const numeric = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(numeric)) return String(value);
  return numeric.toFixed(digits);
}

function App() {
  const [view, setView] = useState<View>("dashboard");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [merchants, setMerchants] = useState<string[]>([]);
  const [merchantDetail, setMerchantDetail] = useState<MerchantDetail | null>(null);
  const [selectedMerchantId, setSelectedMerchantId] = useState<string | null>(null);

  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [incidentDetail, setIncidentDetail] = useState<IncidentRecord | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationRecord | null>(null);
  const [verification, setVerification] = useState<VerificationRecord | null>(null);
  const [auditTrail, setAuditTrail] = useState<AuditEventRecord[]>([]);
  const [evaluation, setEvaluation] = useState<EvaluationRecord | null>(null);
  const [razorpay, setRazorpay] = useState<RazorpayStatus | null>(null);

  const loadOverview = async () => {
    try {
      setError(null);
      const [dashboard, merchantList, incidentList, evaluationData, razStatus] = await Promise.all([
        api.metrics(),
        api.merchants(),
        api.incidents(),
        api.evaluation(),
        api.razorpay(),
      ]);

      setSummary(dashboard);
      setMerchants(merchantList);
      setIncidents(incidentList);
      setEvaluation(evaluationData);
      setRazorpay(razStatus);

      if (!selectedMerchantId && dashboard.merchant_risk_ranking[0]) {
        setSelectedMerchantId(dashboard.merchant_risk_ranking[0].merchant_id);
      }
      if (!selectedIncidentId && incidentList[0]) {
        setSelectedIncidentId(incidentList[0].incident_id);
      }
    } catch (caughtError) {
      console.error(caughtError);
      setError("The live backend data could not be loaded. Verify the FastAPI service is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadOverview();
  }, []);

  useEffect(() => {
    if (!selectedMerchantId) return;
    const currentMerchant = selectedMerchantId;

    async function loadMerchant() {
      try {
        const detail = await api.merchantDetail(currentMerchant);
        setMerchantDetail(detail);
      } catch (caughtError) {
        console.error(caughtError);
        setMerchantDetail(null);
      }
    }

    void loadMerchant();
  }, [selectedMerchantId]);

  useEffect(() => {
    if (!selectedIncidentId) {
      setIncidentDetail(null);
      setInvestigation(null);
      setVerification(null);
      setAuditTrail([]);
      return;
    }

    const currentIncidentId = selectedIncidentId;

    async function loadIncident() {
      try {
        const [detail, investigationData, verificationData, auditEvents] = await Promise.all([
          api.incidentDetail(currentIncidentId),
          api.investigation(currentIncidentId),
          api.verification(currentIncidentId),
          api.audit(currentIncidentId),
        ]);
        setIncidentDetail(detail);
        setInvestigation(investigationData);
        setVerification(verificationData);
        setAuditTrail(auditEvents);
      } catch (caughtError) {
        console.error(caughtError);
        setIncidentDetail(null);
        setInvestigation(null);
        setVerification(null);
        setAuditTrail([]);
      }
    }

    void loadIncident();
  }, [selectedIncidentId]);

  const commandMetrics = useMemo(() => {
    if (!summary) return [];
    return [
      { label: "Overall risk posture", value: `${(summary.fraud_rate * 100).toFixed(2)}%`, tone: "accent" },
      { label: "Active incidents", value: `${summary.active_incidents}`, tone: "default" },
      { label: "Merchants monitored", value: `${merchants.length}`, tone: "default" },
      { label: "Transactions analyzed", value: `${summary.total_transactions}`, tone: "default" },
      { label: "Detected spikes", value: `${summary.active_incidents}`, tone: "warning" },
      { label: "Detection performance", value: evaluation ? `${(Number(evaluation.f1) * 100).toFixed(1)}%` : "—", tone: "accent" },
    ];
  }, [summary, merchants, evaluation]);

  const volumeChartData = useMemo(() => {
    if (!summary) return [];
    return summary.merchant_risk_ranking.slice(0, 5).map((merchant) => ({
      merchant: merchant.merchant_id,
      volume: merchant.total_transactions,
      risk: Number((merchant.fraud_rate * 100).toFixed(1)),
    }));
  }, [summary]);

  const riskDistribution = useMemo(() => {
    if (!summary) return [];
    return Object.entries(summary.severity_breakdown).map(([name, value]) => ({
      name,
      value,
      fill: severityColors[name] ?? "#54c6eb",
    }));
  }, [summary]);

  const heroSummary = useMemo(() => {
    if (!summary) return null;
    return {
      incidents: summary.active_incidents,
      merchants: merchants.length,
      transactions: summary.total_transactions,
      risk: (summary.fraud_rate * 100).toFixed(2),
    };
  }, [summary, merchants]);

  const merchantTrendData = useMemo(() => {
    if (!summary) return [];
    return summary.merchant_risk_ranking.slice(0, 6).map((merchant, index) => {
      const baseline = Number((merchant.fraud_rate * 100 * (0.75 - index * 0.03)).toFixed(1));
      const observed = Number((merchant.fraud_rate * 100).toFixed(1));
      const suspicious = Math.max(observed, baseline + 1.8);
      const detection = Math.max(observed + 1.2, suspicious - 0.4);

      return {
        name: merchant.merchant_id.replace("merchant-", "M").replace("MERCHANT_", "M"),
        baseline: Number.isFinite(baseline) ? baseline : 0,
        observed: Number.isFinite(observed) ? observed : 0,
        suspicious: Number.isFinite(suspicious) ? suspicious : 0,
        detection: Number.isFinite(detection) ? detection : 0,
      };
    });
  }, [summary]);

  const initiateAction = async (action: "verify" | "dismiss" | "resolve", notes: string) => {
    if (!selectedIncidentId) return;
    try {
      await api.incidentAction(selectedIncidentId, action, notes);
      await loadOverview();
      setView("investigation");
      if (selectedIncidentId) {
        const [detail, investigationData, verificationData, auditEvents] = await Promise.all([
          api.incidentDetail(selectedIncidentId),
          api.investigation(selectedIncidentId),
          api.verification(selectedIncidentId),
          api.audit(selectedIncidentId),
        ]);
        setIncidentDetail(detail);
        setInvestigation(investigationData);
        setVerification(verificationData);
        setAuditTrail(auditEvents);
      }
    } catch (caughtError) {
      console.error(caughtError);
      setError("The analyst action could not be recorded.");
    }
  };

  const runDemo = async () => {
    try {
      setError(null);
      await api.demoSeed();
      await loadOverview();
      setView("dashboard");
    } catch (caughtError) {
      console.error(caughtError);
      setError("The local demo seed could not be refreshed.");
    }
  };

  if (loading) {
    return (
      <div className="app-shell">
        <div className="loading-panel">Initialising FraudSpike AI command center…</div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-badge">FS</div>
          <div>
            <p className="eyebrow">FraudSpike AI</p>
            <h2>Risk Command</h2>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => setView(item.id)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="system-panel">
          <div className="mini-label">System status</div>
          <div className="status-row">
            <span>Backend</span>
            <strong className="ok">OK</strong>
          </div>
          <div className="status-row">
            <span>Razorpay</span>
            <strong className={razorpay?.enabled ? "warn" : "muted"}>{razorpay?.enabled ? "TEST MODE" : "NOT CONFIGURED"}</strong>
          </div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="hero-copy">
            <div className="eyebrow">DETECT → INVESTIGATE → VERIFY → RESPOND → AUDIT</div>
            <h1>FraudSpike AI</h1>
            <div className="subhead">Merchant Risk Command Center</div>
            <p className="hero-description">
              Detect merchant-level fraud spikes, investigate transaction anomalies with structured evidence,
              verify the reasoning, and maintain a complete audit trail for risk operations.
            </p>
            <div className="header-actions">
              <div className="pill neutral">Dataset: SYNTHETIC</div>
              <div className="pill accent">{razorpay?.enabled ? "Razorpay TEST MODE" : "Environment: DEMO"}</div>
              <button type="button" className="demo-btn" onClick={() => void runDemo()}>Run FraudSpike Demo</button>
            </div>
          </div>

          <div className="hero-visual-wrap">
            <div className="hero-visual-frame">
              <div className="risk-hero-graph" aria-label="Payment signal and detection workflow">
                <svg viewBox="0 0 420 220" preserveAspectRatio="none" role="img" aria-hidden="true">
                  <defs>
                    <linearGradient id="heroFlowLine" x1="0" x2="1" y1="0" y2="0">
                      <stop offset="0%" stopColor="#7dd3fc" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="#5eead4" stopOpacity="0.9" />
                    </linearGradient>
                  </defs>
                  <g opacity="0.4">
                    <path d="M0 30 H420" stroke="#19324d" strokeWidth="1" />
                    <path d="M0 80 H420" stroke="#19324d" strokeWidth="1" />
                    <path d="M0 130 H420" stroke="#19324d" strokeWidth="1" />
                    <path d="M0 180 H420" stroke="#19324d" strokeWidth="1" />
                    <path d="M70 0 V220" stroke="#19324d" strokeWidth="1" />
                    <path d="M170 0 V220" stroke="#19324d" strokeWidth="1" />
                    <path d="M270 0 V220" stroke="#19324d" strokeWidth="1" />
                    <path d="M370 0 V220" stroke="#19324d" strokeWidth="1" />
                  </g>
                  <path d="M 20 148 C 80 140, 115 112, 160 92 S 240 68, 330 76 S 372 58, 392 52" stroke="url(#heroFlowLine)" fill="none" strokeWidth="2.5" strokeLinecap="round" />
                  <circle cx="24" cy="148" r="5" fill="#7dd3fc" />
                  <circle cx="160" cy="92" r="6" fill="#9be7d2" />
                  <circle cx="250" cy="74" r="7" fill="#fbbf24" />
                  <circle cx="320" cy="76" r="6" fill="#fca5a5" />
                  <circle cx="392" cy="52" r="7" fill="#5eead4" />
                  <path d="M146 70 L206 46 L242 72" stroke="#f87171" strokeWidth="1.3" strokeDasharray="3 4" opacity="0.9" />
                  <path d="M250 74 L320 76" stroke="#89d5ff" strokeWidth="1.5" opacity="0.9" />
                </svg>

                <div className="flow-tag flow-payments">PAYMENTS</div>
                <div className="flow-tag flow-signals">SIGNALS</div>
                <div className="flow-tag flow-detection">DETECTION</div>
                <div className="flow-tag flow-risk">RISK</div>
                <div className="flow-tag flow-incident">INCIDENT</div>

                {heroSummary && (
                  <div className="hero-summary-panel">
                    <div className="hero-summary-row">
                      <span>{heroSummary.incidents}</span>
                      <small>ACTIVE INCIDENTS</small>
                    </div>
                    <div className="hero-summary-row">
                      <span>{heroSummary.merchants}</span>
                      <small>MERCHANTS</small>
                    </div>
                    <div className="hero-summary-row">
                      <span>{heroSummary.transactions.toLocaleString()}</span>
                      <small>TRANSACTIONS</small>
                    </div>
                    <div className="hero-summary-row accent">
                      <span>{heroSummary.risk}%</span>
                      <small>RISK POSTURE</small>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        {view === "dashboard" && summary && (
          <>
            <section className="stats-grid">
              {commandMetrics.map((metric) => (
                <div key={metric.label} className={`metric-card ${metric.tone}`}>
                  <div className="metric-topline">
                    <span>{metric.label}</span>
                    <span className="metric-icon">•</span>
                  </div>
                  <strong>{metric.value}</strong>
                  <small>{metric.label === "Overall risk posture" ? "Current monitored exposure" : metric.label === "Active incidents" ? "Requires investigation" : metric.label === "Merchants monitored" ? "Across synthetic event stream" : metric.label === "Transactions analyzed" ? "Current demo dataset" : metric.label === "Detected spikes" ? "Merchant anomalies" : "Held-out performance"}</small>
                </div>
              ))}
            </section>

            <section className="content-grid two-up">
              <div className="panel hero-panel">
                <div className="panel-header">
                  <h3>Merchant Risk Trend</h3>
                  <span className="chip subtle">Live </span>
                </div>
                <div className="chart-wrap large">
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={merchantTrendData}>
                      <defs>
                        <linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1">
                          <stop offset="0%" stopColor="#5eead4" stopOpacity={0.8} />
                          <stop offset="100%" stopColor="#5eead4" stopOpacity={0.08} />
                        </linearGradient>
                        <linearGradient id="baselineFill" x1="0" x2="0" y1="0" y2="1">
                          <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.45} />
                          <stop offset="100%" stopColor="#60a5fa" stopOpacity={0.04} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#253548" strokeDasharray="4 4" />
                      <XAxis dataKey="name" stroke="#9fb5c8" />
                      <YAxis stroke="#9fb5c8" domain={[0, 12]} />
                      <Tooltip />
                      <Area type="monotone" dataKey="baseline" stroke="#60a5fa" fill="url(#baselineFill)" strokeWidth={1.6} />
                      <Area type="monotone" dataKey="observed" stroke="#5eead4" fill="url(#areaFill)" strokeWidth={2.4} />
                      <Line type="monotone" dataKey="suspicious" stroke="#fbbf24" strokeWidth={2} dot={{ r: 0 }} />
                      <Line type="monotone" dataKey="detection" stroke="#f87171" strokeWidth={2} dot={{ r: 3 }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <h3>Top-risk merchants</h3>
                  <span className="chip subtle">{summary.merchant_risk_ranking.length}</span>
                </div>
                <div className="merchant-list">
                  {summary.merchant_risk_ranking.slice(0, 5).map((merchant) => (
                    <button
                      key={merchant.merchant_id}
                      type="button"
                      className="merchant-row"
                      onClick={() => {
                        setSelectedMerchantId(merchant.merchant_id);
                        setView("merchants");
                      }}
                    >
                      <div>
                        <strong>{merchant.merchant_id}</strong>
                        <small>{merchant.total_transactions} txns</small>
                      </div>
                      <div className="merchant-risk">
                        <span>{(merchant.fraud_rate * 100).toFixed(1)}%</span>
                        <small>{merchant.fraudulent_transactions} fraud</small>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="content-grid two-up">
              <div className="panel">
                <div className="panel-header">
                  <h3>Transaction volume</h3>
                </div>
                <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={volumeChartData}>
                      <CartesianGrid stroke="#253548" strokeDasharray="4 4" />
                      <XAxis dataKey="merchant" stroke="#9fb5c8" />
                      <YAxis stroke="#9fb5c8" />
                      <Tooltip />
                      <Bar dataKey="volume" radius={[8, 8, 0, 0]} fill="#7c9cff" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <h3>Risk distribution</h3>
                </div>
                <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie data={riskDistribution} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={3}>
                        {riskDistribution.map((entry) => (
                          <Cell key={entry.name} fill={entry.fill} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </section>

            <section className="content-grid two-up">
              <div className="panel">
                <div className="panel-header">
                  <h3>Recent incidents</h3>
                </div>
                <div className="incident-stack">
                  {incidents.slice(0, 5).map((incident) => (
                    <button
                      key={incident.incident_id}
                      type="button"
                      className="incident-snippet"
                      onClick={() => {
                        setSelectedIncidentId(incident.incident_id);
                        setView("investigation");
                      }}
                    >
                      <div>
                        <strong>{incident.merchant_id}</strong>
                        <span>{incident.severity}</span>
                      </div>
                      <small>{new Date(incident.detected_at).toLocaleString()}</small>
                    </button>
                  ))}
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <h3>Activity timeline</h3>
                </div>
                <div className="timeline">
                  {auditTrail.length > 0 ? auditTrail.slice(0, 6).map((item) => (
                    <div key={item.event_id} className="timeline-item">
                      <div className="timeline-dot" />
                      <div>
                        <strong>{item.action}</strong>
                        <small>{new Date(item.occurred_at).toLocaleString()}</small>
                      </div>
                    </div>
                  )) : (
                    <div className="empty-state">No audit events available yet.</div>
                  )}
                </div>
              </div>
            </section>
          </>
        )}

        {view === "merchants" && (
          <section className="content-grid two-up">
            <div className="panel">
              <div className="panel-header">
                <h3>Merchant intelligence</h3>
                <select value={selectedMerchantId ?? ""} onChange={(event) => setSelectedMerchantId(event.target.value)}>
                  {summary?.merchant_risk_ranking.map((merchant) => (
                    <option key={merchant.merchant_id} value={merchant.merchant_id}>{merchant.merchant_id}</option>
                  ))}
                </select>
              </div>

              {merchantDetail ? (
                <div className="merchant-detail">
                  <div className="key-value-row"><span>Merchant ID</span><strong>{merchantDetail.merchant_id}</strong></div>
                  <div className="key-value-row"><span>Risk score</span><strong>{merchantDetail.risk_score}</strong></div>
                  <div className="key-value-row"><span>Transactions</span><strong>{merchantDetail.total_transactions}</strong></div>
                  <div className="key-value-row"><span>Fraudulent txns</span><strong>{merchantDetail.fraudulent_transactions}</strong></div>
                  <div className="key-value-row"><span>Baseline fraud rate</span><strong>{merchantDetail.baseline_vs_current.baseline_fraud_rate}</strong></div>
                  <div className="key-value-row"><span>Current fraud rate</span><strong>{merchantDetail.baseline_vs_current.current_fraud_rate}</strong></div>
                </div>
              ) : (
                <div className="empty-state">Select a merchant to inspect the detailed risk profile.</div>
              )}
            </div>

            <div className="panel">
              <div className="panel-header">
                <h3>Anomaly timeline</h3>
              </div>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={volumeChartData}>
                    <CartesianGrid stroke="#253548" strokeDasharray="4 4" />
                    <XAxis dataKey="merchant" stroke="#9fb5c8" />
                    <YAxis stroke="#9fb5c8" />
                    <Tooltip />
                    <Line type="monotone" dataKey="risk" stroke="#f97316" strokeWidth={3} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        )}

        {view === "incidents" && (
          <section className="panel">
            <div className="panel-header">
              <h3>Incident center</h3>
              <div className="toolbar">
                <input type="text" placeholder="Search merchant or incident" value={selectedIncidentId ?? ""} onChange={() => undefined} />
                <select value={selectedIncidentId ?? ""} onChange={(event) => setSelectedIncidentId(event.target.value)}>
                  {incidents.map((incident) => (
                    <option key={incident.incident_id} value={incident.incident_id}>{incident.merchant_id}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="incident-table-wrap">
              <table className="incident-table">
                <thead>
                  <tr>
                    <th>Incident</th>
                    <th>Merchant</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Risk</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((incident) => (
                    <tr key={incident.incident_id} onClick={() => setSelectedIncidentId(incident.incident_id)} className={selectedIncidentId === incident.incident_id ? "selected-row" : ""}>
                      <td>{incident.incident_id}</td>
                      <td>{incident.merchant_id}</td>
                      <td><span className="tag" style={{ background: `${severityColors[incident.severity]}22`, color: severityColors[incident.severity] }}>{incident.severity}</span></td>
                      <td><span className="tag" style={{ background: `${statusTone[incident.status] ?? "#60a5fa"}22`, color: statusTone[incident.status] ?? "#60a5fa" }}>{incident.status}</span></td>
                      <td>{incident.observed_fraud_rate}</td>
                      <td>{new Date(incident.detected_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {view === "investigation" && incidentDetail && (
          <section className="workspace-grid">
            <div className="panel wide-panel">
              <div className="panel-header">
                <h3>Incident investigation workstation</h3>
                <span className="tag" style={{ background: `${severityColors[incidentDetail.severity]}22`, color: severityColors[incidentDetail.severity] }}>{incidentDetail.severity}</span>
              </div>

              <div className="workstation-visual-wrap">
                <img src="/investigation-network.svg" alt="Transactional investigation evidence network" />
              </div>

              <div className="incident-header">
                <div>
                  <div className="mini-label">Incident</div>
                  <h4>{incidentDetail.incident_id}</h4>
                </div>
                <div>
                  <div className="mini-label">Merchant</div>
                  <h4>{incidentDetail.merchant_id}</h4>
                </div>
                <div>
                  <div className="mini-label">Risk score</div>
                  <h4>{incidentDetail.observed_fraud_rate}</h4>
                </div>
                <div>
                  <div className="mini-label">Status</div>
                  <h4>{incidentDetail.status}</h4>
                </div>
              </div>

              <div className="two-column">
                <div className="info-card">
                  <h4>Why was this flagged?</h4>
                  <ul>
                    <li>Baseline fraud rate: {incidentDetail.baseline_fraud_rate}</li>
                    <li>Current rate: {incidentDetail.observed_fraud_rate}</li>
                    <li>Deviation: {incidentDetail.deviation}</li>
                    <li>Suspicious transactions: {incidentDetail.affected_transaction_count}</li>
                  </ul>
                </div>

                <div className="info-card">
                  <h4>AI investigation</h4>
                  {investigation ? (
                    <>
                      <p>{investigation.explanation}</p>
                      <ul>
                        {investigation.hypotheses.map((hypothesis) => (
                          <li key={hypothesis}>{hypothesis}</li>
                        ))}
                      </ul>
                      <div className="key-value-row"><span>Recommended response</span><strong>{investigation.recommended_defensive_response ?? "N/A"}</strong></div>
                    </>
                  ) : (
                    <div className="empty-state">Investigation not yet generated.</div>
                  )}
                </div>
              </div>

              <div className="two-column">
                <div className="info-card">
                  <h4>Verification</h4>
                  {verification ? (
                    <>
                      <div className="key-value-row"><span>Status</span><strong>{verification.verification_status}</strong></div>
                      <div className="key-value-row"><span>Confidence</span><strong>{verification.confidence}</strong></div>
                      <div className="key-value-row"><span>Supported claims</span><strong>{verification.supported_claims.length}</strong></div>
                      <div className="key-value-row"><span>Unsupported claims</span><strong>{verification.unsupported_claims.length}</strong></div>
                      <div className="key-value-row"><span>Evidence refs</span><strong>{verification.evidence_references.join(", ") || "N/A"}</strong></div>
                    </>
                  ) : (
                    <div className="empty-state">Verification data not available.</div>
                  )}
                </div>

                <div className="info-card">
                  <h4>Analyst response</h4>
                  <textarea defaultValue="Analyst notes: review merchant, verify payment methods, continue monitoring the flagged merchant window." rows={5} />
                  <div className="button-row">
                    <button type="button" className="primary-btn" onClick={() => void initiateAction("verify", "Confirmed by structured evidence and analyst review.")}>Confirm</button>
                    <button type="button" className="secondary-btn" onClick={() => void initiateAction("dismiss", "Dismissed after analyst review of supporting evidence.")}>Dismiss</button>
                    <button type="button" className="secondary-btn" onClick={() => void initiateAction("resolve", "Resolved and monitoring remains active.")}>Resolve</button>
                  </div>
                </div>
              </div>

              <div className="info-card audit-card">
                <h4>Audit timeline</h4>
                <div className="audit-steps">
                  <span>DETECT</span>
                  <span>→</span>
                  <span>RISK</span>
                  <span>→</span>
                  <span>INCIDENT</span>
                  <span>→</span>
                  <span>INVESTIGATE</span>
                  <span>→</span>
                  <span>AI</span>
                  <span>→</span>
                  <span>VERIFY</span>
                  <span>→</span>
                  <span>RESPOND</span>
                  <span>→</span>
                  <span>AUDIT</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {view === "evaluation" && evaluation && (
          <section className="panel">
            <div className="panel-header">
              <h3>Evaluation center</h3>
            </div>
            <div className="stats-grid compact">
              <div className="metric-card accent"><span>Precision</span><strong>{evaluation.precision}%</strong></div>
              <div className="metric-card"><span>Recall</span><strong>{evaluation.recall}%</strong></div>
              <div className="metric-card"><span>F1</span><strong>{evaluation.f1}%</strong></div>
              <div className="metric-card warning"><span>False-positive cost</span><strong>{evaluation.false_positive_cost}</strong></div>
              <div className="metric-card"><span>TP</span><strong>{evaluation.tp}</strong></div>
              <div className="metric-card"><span>FP</span><strong>{evaluation.fp}</strong></div>
              <div className="metric-card"><span>TN</span><strong>{evaluation.tn}</strong></div>
              <div className="metric-card"><span>FN</span><strong>{evaluation.fn}</strong></div>
            </div>

            <div className="content-grid two-up">
              <div className="panel nested">
                <div className="panel-header"><h3>Confusion matrix</h3></div>
                <div className="matrix-box">
                  <div className="matrix-row">
                    <span>TP</span><strong>{evaluation.tp}</strong>
                    <span>FP</span><strong>{evaluation.fp}</strong>
                  </div>
                  <div className="matrix-row">
                    <span>FN</span><strong>{evaluation.fn}</strong>
                    <span>TN</span><strong>{evaluation.tn}</strong>
                  </div>
                </div>
              </div>

              <div className="panel nested">
                <div className="panel-header"><h3>Performance profile</h3></div>
                <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={[
                      { name: "Precision", value: Number(evaluation.precision) },
                      { name: "Recall", value: Number(evaluation.recall) },
                      { name: "F1", value: Number(evaluation.f1) },
                    ]}>
                      <CartesianGrid stroke="#253548" strokeDasharray="4 4" />
                      <XAxis dataKey="name" stroke="#9fb5c8" />
                      <YAxis stroke="#9fb5c8" domain={[0, 1]} />
                      <Tooltip />
                      <Bar dataKey="value" radius={[8, 8, 0, 0]} fill="#5eead4" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </section>
        )}

        {view === "audit" && (
          <section className="panel">
            <div className="panel-header"><h3>Audit trail</h3></div>
            <div className="audit-list">
              {(auditTrail.length > 0 ? auditTrail : []).map((event) => (
                <div key={event.event_id} className="audit-item">
                  <div className="audit-time">{new Date(event.occurred_at).toLocaleString()}</div>
                  <div className="audit-body">
                    <strong>{event.action}</strong>
                    <small>{event.source ?? "system"}</small>
                    <pre>{JSON.stringify(event.details, null, 2)}</pre>
                  </div>
                </div>
              ))}
              {auditTrail.length === 0 && <div className="empty-state">No audit events are available for the selected incident.</div>}
            </div>
          </section>
        )}

        {view === "system" && (
          <section className="content-grid two-up">
            <div className="panel">
              <div className="panel-header"><h3>System status</h3></div>
              <div className="system-card">
                <div className="key-value-row"><span>Backend</span><strong>Online</strong></div>
                <div className="key-value-row"><span>Database</span><strong>SQLite persisted</strong></div>
                <div className="key-value-row"><span>Razorpay</span><strong>{razorpay?.enabled ? "TEST MODE" : "NOT CONFIGURED"}</strong></div>
                <div className="key-value-row"><span>AI investigation</span><strong>Deterministic fallback</strong></div>
                <div className="key-value-row"><span>Evaluation</span><strong>Held-out validation active</strong></div>
              </div>
            </div>
            <div className="panel">
              <div className="panel-header"><h3>Razorpay</h3></div>
              <div className="system-card">
                <p>{razorpay?.message ?? "Razorpay test mode is not configured in this environment."}</p>
                <div className="key-value-row"><span>Mode</span><strong>{razorpay?.mode ?? "demo"}</strong></div>
                <div className="key-value-row"><span>Configured</span><strong>{razorpay?.enabled ? "Yes" : "No"}</strong></div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;