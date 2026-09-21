// apps/extension/src/types/server-protocol.ts
//
// Clean message types for the extension ↔ service-worker ↔ SLM server pipeline.
// This file replaces native-protocol.ts entirely.  There is no longer any
// native daemon; all inference is handled by the remote SLM server.

// ─── Audit report (matches the server's validated DpdpAuditReport schema) ────
// The set of enforcement directives a violation's network_action can carry -
// matches every case actually handled in dark-pattern-blocker.ts's switch
// statement. Violation.network_action itself stays a plain string (server
// response field, shouldn't hard-fail parsing on an unrecognized future
// value), but call sites that need to switch on it exhaustively cast through
// this narrower type.
export type NetworkAction =
  | 'BLOCK_THIRD_PARTY'
  | 'WARN_USER_ONLY'
  | 'STRIP_TELEMETRY_HEADER'
  | 'INJECT_GPC_SIGNAL'
  | 'SPOOF_HARDWARE_API';

export interface Violation {
  violation_type: string;
  statute_reference: string;
  evidence_quote: string;
  network_action: string;
  offending_entities: string[];
  step_1_active_claim_analysis?: string;
  step_2_statute_match?: string;
  step_3_semantic_justification?: string;
  omission_check?: boolean;
}

export interface ExplainabilityFeature {
  feature: string;
  shap_value: number | string;
  evidence?: string;
}

export interface Explainability {
  method: string;
  features?: ExplainabilityFeature[];
}

export interface AuditReport {
  dpdp_trust_score: number;
  subtlety_score: number;
  violations: Violation[];
  global_legal_reasoning: string;
  explainability?: Explainability;
}

// ─── Server response shapes ───────────────────────────────────────────────────
export interface AuditServerResponse {
  source: 'persistent_cache' | 'hot_cache' | 'inference' | 'memory_cache' | string;
  data: AuditReport;
  cached_at?: number | null;
  age_days?: number | null;
}

// ─── Internal extension message bus (service-worker ↔ UI) ────────────────────
/** Chat-only quota info — audits are never rate-limited, so this never appears on audit responses. */
export interface RateLimitInfo { limit: number; remaining: number; windowSeconds: number; }

export type ServiceResponse =
  | { type: 'AUDIT_POLICY_RESULT'; requestId: string; success: true; report: AuditReport; cached: boolean }
  | { type: 'CHAT_RESULT'; requestId: string; success: true; message: string; rateLimit?: RateLimitInfo }
  | { type: 'HEALTH_CHECK_RESULT'; requestId: string; success: boolean; modelLoaded: boolean; cacheSize: number; totalInferences: number; avgTokensPerSecond: number; hasGpuAcceleration: false }
  | { type: 'ERROR'; requestId: string; success: false; error: string; errorKind?: string; retryable?: boolean; rateLimit?: RateLimitInfo };

export type ChatResponseMode = 'concise' | 'thinking';

// ─── Re-export under legacy names so callsites don't need mass-updating ───────
/** @deprecated  Use AuditReport directly. */
export type DpdpAuditReport = AuditReport;
/** @deprecated  Use ServiceResponse directly. */
export type DaemonResponse = ServiceResponse;
