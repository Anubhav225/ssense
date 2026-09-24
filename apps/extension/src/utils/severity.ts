// apps/extension/src/utils/severity.ts
//
// The audit engine returns a violation *type* and a statute reference but not a
// severity. For the History/Popup views we group violations by impact so users
// see the serious ones first. This mapping is a client-side presentation aid —
// it never changes the audit result or the trust score.

import type { Violation } from '../types/server-protocol';

export type Severity = 'high' | 'medium' | 'low';

const HIGH = new Set([
  'CONSENT_NOT_FREE_OR_SPECIFIC',
  'CHILD_CONSENT_VIOLATION',
  'CROSS_BORDER_TRANSFER_VIOLATION',
  'SECURITY_SAFEGUARDS_MISSING',
  'BREACH_NOTIFICATION_FAILURE',
  'PURPOSE_LIMITATION_VIOLATION',
  'SDF_DATA_LOCALIZATION_VIOLATION',
]);

const LOW = new Set([
  'NOTICE_INADEQUATE',
  'GRIEVANCE_REDRESSAL_INADEQUATE',
]);

export function severityOf(v: Pick<Violation, 'violation_type' | 'network_action'>): Severity {
  const t = (v.violation_type || '').toUpperCase();
  if (HIGH.has(t)) return 'high';
  if (LOW.has(t)) {
    // A low-impact finding that also triggers active blocking of third parties
    // is more than a paperwork gap.
    return v.network_action === 'BLOCK_THIRD_PARTY' || v.network_action === 'SPOOF_HARDWARE_API' ? 'medium' : 'low';
  }
  return 'medium';
}

export const SEVERITY_ORDER: Severity[] = ['high', 'medium', 'low'];

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: 'High impact',
  medium: 'Medium impact',
  low: 'Low impact',
};

export function groupBySeverity<T extends Pick<Violation, 'violation_type' | 'network_action'>>(
  violations: T[],
): Record<Severity, T[]> {
  const out: Record<Severity, T[]> = { high: [], medium: [], low: [] };
  for (const v of violations || []) out[severityOf(v)].push(v);
  return out;
}

export function prettyViolationType(t: string): string {
  return (t || 'Unknown').toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function prettyAction(a: string): string {
  const map: Record<string, string> = {
    BLOCK_THIRD_PARTY: 'Third-party blocked',
    WARN_USER_ONLY: 'Warning only',
    STRIP_TELEMETRY_HEADER: 'Telemetry stripped',
    INJECT_GPC_SIGNAL: 'GPC signal sent',
    SPOOF_HARDWARE_API: 'Fingerprinting masked',
  };
  return map[a] || (a || '').toLowerCase().replace(/_/g, ' ');
}
