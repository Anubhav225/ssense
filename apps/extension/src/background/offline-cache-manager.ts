// apps/extension/src/background/offline-cache-manager.ts
//
// Manages offline-first audit resolution, Stale-While-Revalidate (SWR),
// and background cache warming for the top-visited sites.

import * as auditCache from './audit-cache';
import type { LocalAuditEntry } from './audit-cache';
import { executeFetchCachedAudit, executeAuditByUrl } from './api-client';
import * as historyStore from './history-store';

export interface AuditResultWithMeta {
  entry:     LocalAuditEntry | null;
  source:    'offline_cache' | 'persistent_cache' | 'inference' | 'local_cache';
  isOffline: boolean;
  isStale:   boolean;
  ageDays:   number;
}

const STALE_THRESHOLD_MS = 6 * 60 * 60 * 1000; // 6 hours

export function isOnline(): boolean {
  return typeof navigator !== 'undefined' ? navigator.onLine : true;
}

/**
 * Reads local cache immediately. If online and older than STALE_THRESHOLD_MS,
 * schedules a background server re-validation without blocking UI display.
 */
export async function getAuditSWR(domain: string, policyUrl?: string): Promise<AuditResultWithMeta> {
  const norm = auditCache.normaliseDomain(domain);
  const local = await auditCache.getAudit(norm);
  const offline = !isOnline();

  if (local) {
    const ageMs = Date.now() - (local.audited_at || 0);
    const isStale = ageMs > STALE_THRESHOLD_MS;

    // If offline, return immediately as offline cache
    if (offline) {
      return {
        entry: local,
        source: 'offline_cache',
        isOffline: true,
        isStale,
        ageDays: Math.round((ageMs / (24 * 3600 * 1000)) * 10) / 10,
      };
    }

    // If online and stale, revalidate in background
    if (isStale && policyUrl) {
      _revalidateInBackground(norm, policyUrl).catch(() => {});
    }

    return {
      entry: local,
      source: (local.source as any) || 'local_cache',
      isOffline: false,
      isStale,
      ageDays: Math.round((ageMs / (24 * 3600 * 1000)) * 10) / 10,
    };
  }

  // No local entry
  return {
    entry: null,
    source: offline ? 'offline_cache' : 'inference',
    isOffline: offline,
    isStale: false,
    ageDays: 0,
  };
}

async function _revalidateInBackground(domain: string, policyUrl: string): Promise<void> {
  try {
    const reqId = crypto.randomUUID();
    const res = await executeAuditByUrl(domain, policyUrl, reqId, false);
    if (res.type === 'AUDIT_POLICY_RESULT' && res.success && res.report) {
      const saved = await auditCache.saveAudit(domain, res.report, {
        policy_url: policyUrl,
        source: res.cached ? 'persistent_cache' : 'inference',
      });
      await historyStore.recordAudit(domain, res.report);
      // Notify listening UI tabs that a fresh audit arrived
      chrome.runtime.sendMessage({
        type: 'AUDIT_COMPLETE',
        domain,
        score: res.report.dpdp_trust_score,
        report: res.report,
        source: saved.source,
      }).catch(() => {});
    }
  } catch (err) {
    console.debug('[OfflineCache] Background revalidation failed (non-fatal):', err);
  }
}

/**
 * On extension startup, pre-warm the top 10 most visited domains from history
 * by fetching their cached server audit if missing or older than 1 day.
 */
export async function warmTopDomainCaches(): Promise<void> {
  if (!isOnline()) return;
  try {
    const history = await historyStore.getAllEntries();
    if (!history || history.length === 0) return;

    // Pick top 10 by visitCount
    const topDomains = history
      .sort((a, b) => (b.visitCount || 0) - (a.visitCount || 0))
      .slice(0, 10)
      .map(e => e.domain);

    for (const domain of topDomains) {
      const local = await auditCache.getAudit(domain);
      const isOld = !local || (Date.now() - local.audited_at > 24 * 60 * 60 * 1000);
      if (isOld) {
        try {
          const reqId = crypto.randomUUID();
          const r = await executeFetchCachedAudit(domain, reqId);
          if (r.type === 'AUDIT_POLICY_RESULT' && r.success && r.report) {
            await auditCache.saveAudit(domain, r.report, { source: 'persistent_cache' });
          }
        } catch {
          // Non-fatal prefetch failure
        }
      }
    }
    console.log('[OfflineCache] Top domain cache pre-warming completed.');
  } catch (err) {
    console.debug('[OfflineCache] Cache warming skipped:', err);
  }
}
