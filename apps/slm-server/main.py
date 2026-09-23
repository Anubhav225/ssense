#!/usr/bin/env python3
"""
main.py — Ssense SLM Server  (v6 — server-side extraction, no policy text in DB)

Architecture changes in this version:
  - Policy text NEVER stored.  The server fetches, extracts, runs inference,
    then discards the raw text.  Only the audit report + a pre-computed chat
    context string are persisted (audit_store.py).
  - New primary audit endpoint: POST /v1/audit/by-url
      Extension sends {domain, policyUrl} — server does everything else.
      Cache lookup order:
        1. Hot in-memory layer   (sub-ms)
        2. SQLite by domain      (90-day TTL)
        3. Policy-hash shortcut  (unchanged policy → same result, any age)
        4. Server fetches URL, extracts text
        5. Hash check against stored hash (re-fetch hit → skip inference)
        6. Inference             (only on genuine miss or force_refresh)
  - Legacy POST /v1/audit (with policyText in body) kept for backward compat.
  - Chat endpoint reads pre-computed chat_context from audit_store — no
    JSON parsing or translate_audit_for_prompt() call on hot path.
  - Audit endpoints: NO rate limit (shared cache absorbs compute cost).
  - Chat endpoint:   rate-limited (60 req/min per api_key+IP).
"""

import asyncio
import json
import os
import re
import sys
import time
import uuid
import numpy as np
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded

import db_sync
from audit_store import audit_store
from engine import ProductionAsyncEngine, detect_hardware_capabilities
from memory_orchestrator import memory_orchestrator, QueueSaturatedError
from multi_user_session import multi_user_session_manager
from policy_fetcher import fetch_policy, FetchResult, close_shared_clients as close_policy_fetch_clients
from rag_engine import rag_engine
from security import (
    _rate_limit_exceeded_handler,
    check_model_extraction_attempt,
    get_client_ip,
    get_dpdp_schema,
    limiter,
    sanitize_input_prompt,
    validate_and_repair_report,
    verify_hmac_signature,
    verify_hmac_signature_chat,
)

llm_engine: Optional[Any] = None
COMPUTE_PROFILE_ENV = os.getenv("SSENSE_COMPUTE_PROFILE", "auto").strip().lower()
if COMPUTE_PROFILE_ENV in ("", "auto"):
    COMPUTE_PROFILE = detect_hardware_capabilities()
    print(f"🔍 [Boot] Hardware auto-detected compute profile: '{COMPUTE_PROFILE}'")
else:
    COMPUTE_PROFILE = COMPUTE_PROFILE_ENV

CHAT_MAX_TOKENS_CONCISE  = 300
CHAT_MAX_TOKENS_THINKING = 2048


# ── Model downloader ──────────────────────────────────────────────────────────
def ensure_models_exist():
    default_models = (
        Path("/app/models")
        if Path("/app/models").exists()
        else (Path(__file__).resolve().parent.parent.parent / "ml" / "models")
    )
    models_dir      = Path(os.getenv("MODELS_DIR", str(default_models)))
    base_model_dir  = models_dir / "base" / "Qwen2.5-7B-Instruct"
    ssense_repo     = "PRiyanshu0-1/DPDP-SSense"

    print("🔍 [Boot] Verifying AI weights and indices...")
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    from huggingface_hub import snapshot_download

    if not base_model_dir.exists() or not list(base_model_dir.glob("*.safetensors")):
        print(f"📥 [Boot] Downloading Qwen2.5-7B-Instruct → {base_model_dir}...")
        snapshot_download(
            repo_id="Qwen/Qwen2.5-7B-Instruct", local_dir=base_model_dir,
            ignore_patterns=["*.pt", "*.bin", "*.h5"],
        )

    # Relocate any already-downloaded content sitting in a nested models/models/
    # subfolder BEFORE checking whether a download is needed. Previously this
    # only ran AFTER a fresh download call, so content left nested by an
    # earlier interrupted/partial run was never found - the flat-path check
    # below would see nothing, and every restart re-triggered a full download.
    import shutil
    nested = models_dir / "models"
    if nested.exists() and nested.is_dir():
        print("📦 [Boot] Found previously downloaded content in a nested folder — moving into place...")
        for item in nested.iterdir():
            target = models_dir / item.name
            if not target.exists():
                shutil.move(str(item), str(target))
        try:
            nested.rmdir()  # only removes it if now empty; leaves it otherwise rather than deleting anything unexpected
        except OSError:
            pass

    audit_adapter = models_dir / "audit-model-final-adapter"
    if not audit_adapter.exists() or not list(audit_adapter.glob("*.safetensors")):
        print(f"📥 [Boot] Downloading Ssense adapters from {ssense_repo}...")
        snapshot_download(
            repo_id=ssense_repo, local_dir=models_dir,
            allow_patterns=["models/*"], ignore_patterns=["*.gguf"],
            local_dir_use_symlinks=False,
        )
        nested = models_dir / "models"
        if nested.exists():
            for item in nested.iterdir():
                target = models_dir / item.name
                if not target.exists():
                    shutil.move(str(item), str(target))
            nested.rmdir()

    print("✅ [Boot] All AI weights verified.")
    return (
        base_model_dir,
        models_dir / "audit-model-final-adapter",
        models_dir / "chatbot-model-final-adapter",
    )


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_engine
    print("🚀 Booting Ssense SLM Server v6 (server-side extraction)...")

    # Auto-import BEFORE audit_store opens the local DB file: if this is a
    # freshly-provisioned instance (empty ./data/db) and a prior export
    # exists at SSENSE_DB_EXPORT_PATH, the shared cache is pulled in here so
    # the server starts warm instead of cold. No-op if export isn't
    # configured, or if this instance already has its own local data — see
    # db_sync.py's docstring for the full safety rules.
    db_sync.import_if_new(audit_store._db_path)

    await memory_orchestrator.verify_rate_limiter_backend()
    await audit_store.initialize()
    base_dir, audit_dir, chat_dir = ensure_models_exist()
    await rag_engine.initialize()

    llm_engine = ProductionAsyncEngine(
        base_model_path=str(base_dir),
        audit_adapter_path=str(audit_dir),
        chatbot_adapter_path=str(chat_dir),
        compute_profile=COMPUTE_PROFILE,
    )

    # Background periodic export → SSENSE_DB_EXPORT_PATH (no-op if unset).
    sync_task = asyncio.create_task(db_sync.periodic_export_task(audit_store._db_path))

    print("✅ Ssense SLM Server ready.")
    yield
    print("🛑 Shutting down...")
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    await db_sync.final_export(audit_store._db_path)
    await audit_store.close()
    await close_policy_fetch_clients()
    if hasattr(rag_engine, "thread_pool"):
        rag_engine.thread_pool.shutdown(wait=False)


app = FastAPI(
    title="Ssense SLM Server",
    description="DPDP Act 2023 auditing — server-side extraction, 90-day shared cache.",
    version="6.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("SSENSE_ALLOWED_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    # Custom response headers are invisible to browser fetch() JS by default
    # (only a fixed CORS "safelist" is exposed cross-origin) — without this,
    # the rate-limit headers below would be sent but silently unreadable by
    # api-client.ts, and the UI would have no way to show remaining chat quota.
    expose_headers=[
        "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Window",
        "X-DailyLimit-Limit", "X-DailyLimit-Remaining", "X-DailyLimit-Reset",
        "X-Ssense-Audit-Remaining", "Retry-After",
    ],
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ── Request models ─────────────────────────────────────────────────────────────
class AuditByUrlRequest(BaseModel):
    domain:        str  = Field(..., description="Target website domain")
    policyUrl:     str  = Field(..., description="Direct URL to the privacy policy page")
    force_refresh: bool = Field(False, description="Bypass cache and re-fetch/re-audit")


class AuditByTextRequest(BaseModel):
    """Legacy: extension sends extracted policy text. Still supported."""
    domain:        str  = Field(...)
    policyText:    str  = Field(...)
    force_refresh: bool = Field(False)


class ChatRequest(BaseModel):
    domain:       str = Field(...)
    userPrompt:   str = Field(...)
    responseMode: str = Field("concise")


# ── Shared audit helpers ───────────────────────────────────────────────────────
_DPDP_KEYWORD_PATTERNS = {
    "consent_purpose": re.compile(r"consent|purpose|legitimate|opt-in|opt-out|withdraw|freely given", re.I),
    "sharing_tracking": re.compile(r"third-party|third party|share|disclose|broker|advertis|cookie|tracker|pixel|sdk", re.I),
    "retention_security": re.compile(r"retain|retention|indefinitely|storage|period|security|breach|safeguard|erasure|delete", re.I),
    "children_transfer": re.compile(r"child|children|minor|age|parental|cross-border|international|overseas|foreign server|transfer", re.I),
    "rights_grievance": re.compile(r"rights|grievance|officer|dpo|nodal|complaint|appeal|board|data protection officer", re.I),
}


# Common abbreviations that a naive "split after . ! ?" regex mistakes for
# sentence ends (privacy policies are full of these: "U.S.", "Inc.", "e.g.",
# "Dept.", statute references like "Sec. 8", etc). Used by
# _split_into_sentences' merge-back pass below.
_SENTENCE_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "etc", "eg", "ie",
    "inc", "ltd", "co", "corp", "us", "uk", "eu", "no", "vol", "fig",
    "approx", "dept", "est", "art", "sec", "para", "cl", "govt", "assn",
    "gov", "rev", "std", "reg", "eqn",
}


def _split_into_sentences(text: str) -> list[str]:
    """Regex sentence splitter with an abbreviation-aware merge-back pass.

    A plain `re.split(r'(?<=[.!?])\\s+', text)` treats "the U.S. Department"
    as two sentences ("...the U.S." / "Department..."), which is exactly
    the kind of false sentence-boundary that made the old chunker's
    "sentence-safe" packing less reliable than it looked — every character
    was preserved somewhere, but semantically-connected clauses could still
    land in different chunks. Python regex lookbehind must be fixed-width,
    so a known-abbreviation set can't be built into the split pattern
    directly; instead this splits naively first, then walks the pieces and
    merges a split back together when the preceding fragment ends in a
    known abbreviation, a single-letter initial ("J. Smith"), or a decimal
    number ("3.5 million") — the standard trick for abbreviation-aware
    sentence splitting without a full NLP dependency.
    """
    if not text:
        return []
    raw_parts = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(raw_parts) <= 1:
        return [p for p in raw_parts if p]

    sentences: list[str] = []
    buf = raw_parts[0]
    for part in raw_parts[1:]:
        prev = buf.rstrip()
        # Matches trailing tokens with internal periods too ("U.S", "e.g"),
        # not just a single final word — a plain `[A-Za-z]+\.$` only ever
        # captures the LAST letter run ("S." out of "U.S."), which missed
        # exactly the multi-period abbreviations ("U.S.", "e.g.") most
        # likely to cause a false sentence break in policy text.
        word_match = re.search(r'((?:[A-Za-z]\.)*[A-Za-z]+)\.$', prev)
        is_known_abbrev = False
        if word_match:
            token = word_match.group(1).replace(".", "").lower()
            is_known_abbrev = token in _SENTENCE_ABBREVIATIONS
        is_single_letter_initial = bool(re.search(r'(?:^|\s)[A-Z]\.$', prev))
        is_decimal_number = bool(re.search(r'\d\.$', prev)) and bool(re.match(r'^\d', part))
        if is_known_abbrev or is_single_letter_initial or is_decimal_number:
            buf = f"{buf} {part}"
        else:
            sentences.append(buf)
            buf = part
    sentences.append(buf)
    return sentences


def chunk_policy_text(
    text: str,
    max_chunk_chars: int = 3200,
    overlap_sentences: int = 2,
) -> list[str]:
    """Splits policy text into coherent, sentence-safe segments of at most
    ~max_chunk_chars, with a small trailing-sentence overlap carried into
    the start of the next chunk for cross-boundary context.

    Two-level strategy:
      1. Split on blank-line paragraph boundaries first (`\\n\\s*\\n`) — the
         common case for well-formatted policy text, and it keeps whole
         paragraphs together where possible, which reads more naturally to
         the model than arbitrary sentence-level joins.
      2. Any paragraph that's STILL over max_chunk_chars on its own (a
         single giant run-on paragraph, or — very common for scraped-from-
         HTML policy text — a document with no blank lines separating
         sections at all, which makes step 1 return one giant "paragraph"
         covering the whole document) is subdivided at SENTENCE boundaries
         via `_split_into_sentences`, never mid-sentence and never mid-word.

    Final chunks are then packed by greedily filling up to max_chunk_chars
    from these paragraph/sentence-level units — packing only ever ends a
    chunk exactly between two such units, so no unit (and therefore no
    sentence) is ever split across the max_chunk_chars boundary either.

    `overlap_sentences` (default 2): after chunks are built, the last N
    sentences of chunk i are prepended to chunk i+1, clearly labeled as
    carried-over context. This directly targets the "properly recombined to
    receive the complete context" requirement — without it, a violation
    whose full meaning depends on the sentence immediately before a chunk
    boundary (e.g. "...as described above. This data is retained
    indefinitely.") can read as ambiguous or lose its antecedent when a
    chunk is evaluated in isolation. Set to 0 to disable.
    """
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]

    # If any individual paragraph exceeds max_chunk_chars, subdivide it at
    # SENTENCE boundaries (never mid-sentence, never mid-word).
    normalized_paragraphs: list[str] = []
    for p in paragraphs:
        if len(p) <= max_chunk_chars:
            normalized_paragraphs.append(p)
        else:
            sub_parts = _split_into_sentences(p)
            buf: list[str] = []
            buf_len = 0
            for part in sub_parts:
                if buf_len + len(part) + 1 > max_chunk_chars and buf:
                    normalized_paragraphs.append(" ".join(buf))
                    buf = [part]
                    buf_len = len(part)
                else:
                    buf.append(part)
                    buf_len += len(part) + 1
            if buf:
                normalized_paragraphs.append(" ".join(buf))

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for p in normalized_paragraphs:
        p_len = len(p)
        if current_len + p_len + 2 > max_chunk_chars and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_len = p_len
        else:
            current.append(p)
            current_len += p_len + 2
    if current:
        chunks.append("\n\n".join(current))

    if overlap_sentences <= 0 or len(chunks) <= 1:
        return chunks

    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_sentences = _split_into_sentences(chunks[i - 1])
        tail = " ".join(prev_sentences[-overlap_sentences:]).strip()
        if tail:
            overlapped.append(
                f"[...continued from previous section, for context: \"{tail}\"]\n\n{chunks[i]}"
            )
        else:
            overlapped.append(chunks[i])
    return overlapped


def _audit_max_chunks_for_profile() -> int:
    """Safety/cost CEILING on how many sections a single audit will evaluate
    — NOT a routine truncation. Previously this was a hardcoded 2 (CPU) / 4
    (GPU) and silently dropped every section beyond it with no warning; a
    ~3200-char chunk size means any policy over ~6,400 chars (CPU) or
    ~12,800 chars (GPU) — well within normal length for a real corporate
    privacy policy — had sections the model never saw, so a violation
    stated only in a skipped section was simply never found. Raised to
    generous per-profile defaults so the common case is full coverage (see
    _run_inference: chunks at or under this cap are evaluated in full,
    ALL of them, in original document order — this cap only bites, and
    only then falls back to keyword-density prioritization, for genuinely
    unusual document lengths). Still env-tunable per deployment since "how
    much to spend evaluating one very long policy" is a real cost/latency
    tradeoff, especially on the CPU profile.
    """
    if COMPUTE_PROFILE == "cpu":
        return int(os.getenv("SSENSE_AUDIT_MAX_CHUNKS_CPU", "1"))
    return int(os.getenv("SSENSE_AUDIT_MAX_CHUNKS_GPU", "20"))


def select_operative_chunks(chunks: list[str], max_chunks: int = 2) -> list[tuple[int, str]]:
    """Prioritizes chunks by statutory legal clause density — used ONLY as a
    fallback when a policy's chunk count exceeds _audit_max_chunks_for_profile()
    (see that function's docstring). In the normal case (chunks within the
    cap), callers should evaluate every chunk directly rather than calling
    this at all, so no section is ever skipped without it being logged."""
    if max_chunks <= 0:
        return []
    if len(chunks) <= max_chunks:
        return list(enumerate(chunks))

    scored = []
    for idx, c in enumerate(chunks):
        coverage = sum(1 for pat in _DPDP_KEYWORD_PATTERNS.values() if pat.search(c))
        density = sum(len(pat.findall(c)) for pat in _DPDP_KEYWORD_PATTERNS.values())
        score = coverage * 10 + min(density, 20)
        scored.append((idx, score, c))

    scored.sort(key=lambda x: x[1], reverse=True)
    selected = scored[:max_chunks]
    selected.sort(key=lambda x: x[0])
    return [(idx, c) for idx, _, c in selected]


def recombine_audit_reports(chunk_reports: list[Dict[str, Any]], domain: str) -> Dict[str, Any]:
    """Deterministically (no LLM call) fuses the violations from N flagged
    chunk reports into one deduplicated, congregated DPDP audit report.

    Called by _run_inference only on the subset of chunks that were already
    flagged (score < 100 and/or non-empty violations) — clean chunks are
    filtered out before this function ever sees them, so `chunk_reports`
    here should essentially never be empty and its "no violations survived
    dedup" branch below is a defensive edge case, not the expected path.
    """
    all_violations = []
    reasonings = []

    for r in chunk_reports:
        reasoning = r.get("global_legal_reasoning", "").strip()
        if reasoning and "No explicit, active contradictions" not in reasoning and reasoning not in reasonings:
            reasonings.append(reasoning)
        for v in r.get("violations", []):
            if isinstance(v, dict) and not v.get("omission_check", False):
                all_violations.append(v)

    unique_violations = []
    seen = set()
    for v in all_violations:
        key = (v.get("violation_type", ""), v.get("statute_reference", ""))
        if key in seen:
            continue
        seen.add(key)
        unique_violations.append(v)

    SEVERITY_DEDUCTIONS = {
        "PURPOSE_LIMITATION_VIOLATION": 15,
        "CONSENT_NOT_FREE_OR_SPECIFIC": 15,
        "CONSENT_MECHANICS_VIOLATION": 15,
        "CROSS_BORDER_TRANSFER_VIOLATION": 15,
        "SDF_DATA_LOCALIZATION_VIOLATION": 15,
        "CHILD_CONSENT_VIOLATION": 15,
        "LEGITIMATE_USES_ABUSE": 12,
        "NOTICE_INADEQUATE": 10,
        "DATA_RETENTION_LIMIT_EXCEEDED": 10,
        "SECURITY_SAFEGUARDS_MISSING": 10,
        "GRIEVANCE_REDRESSAL_INADEQUATE": 10,
        "PROCESSOR_ACCOUNTABILITY_VIOLATION": 10,
    }

    if not unique_violations:
        # Edge case only: every input here was pre-flagged by _run_inference,
        # so ending up with zero violations after dedup means the flagged
        # chunks' violations were all omission_check entries filtered out
        # above. 100 matches the model's own convention for a clean result
        # (see tests/test_server_security.py) rather than an arbitrary
        # different number for this path.
        dpdp_trust_score = 100
        subtlety_score = 0
        global_reasoning = (
            f"Comprehensive multi-section forensic audit of {domain} under the DPDP Act 2023 "
            "and DPDP Rules 2025 revealed no active statutory contradictions in operative policy text."
        )
    else:
        deduction = sum(SEVERITY_DEDUCTIONS.get(v.get("violation_type", ""), 8) for v in unique_violations)
        dpdp_trust_score = max(5, 100 - deduction)
        subtlety_score = max(chunk_r.get("subtlety_score", 0) for chunk_r in chunk_reports) if chunk_reports else 60
        if subtlety_score == 0:
            subtlety_score = 75

        violation_names = ", ".join(v.get("violation_type", "").replace("_", " ").title() for v in unique_violations)
        reasons_text = " ".join(reasonings[:2]) if reasonings else ""
        global_reasoning = (
            f"Forensic audit of {domain} across operative legal sections identified {len(unique_violations)} "
            f"statutory violation(s) under the DPDP Act 2023: {violation_names}. {reasons_text}"
        ).strip()

    return {
        "global_legal_reasoning": global_reasoning,
        "violations": unique_violations,
        "dpdp_trust_score": dpdp_trust_score,
        "subtlety_score": subtlety_score,
    }


def _build_audit_prompt(domain: str, clean_text: str) -> str:
    # BUG FIX: this used to blindly re-slice to [:3200] regardless of what
    # was passed in. `clean_text` here is always ONE chunk already produced
    # by chunk_policy_text() — sentence-safe and bounded to ~max_chunk_chars
    # plus a small overlap allowance (see that function's docstring) — so
    # re-slicing at a flat 3200 was at best redundant and at worst actively
    # harmful: it silently cut off the overlap context chunk_policy_text had
    # just carefully added, and did so with a blind character slice, which
    # could land mid-sentence even though the chunker itself never would.
    # What remains is a generous backstop (well above max_chunk_chars +
    # overlap) that should essentially never trigger in normal operation —
    # a true last-resort safety net, not a routine truncation step.
    max_chars = 1800 if COMPUTE_PROFILE == "cpu" else 4500
    policy_slice = clean_text[:max_chars].strip()
    sys_msg = (
        "You are an expert DPDP Act 2023 forensic legal auditor. "
        "Analyze the provided corporate privacy policy for statutory violations under the "
        "Digital Personal Data Protection Act 2023 and DPDP Rules 2025. "
        "Output ONLY a valid JSON object strictly matching the schema contract."
    )
    user_msg = f"[POLICY TO AUDIT: {domain}]\n{policy_slice}"
    return (
        f"<|im_start|>system\n{sys_msg}<|im_end|>\n"
        f"<|im_start|>user\n{user_msg}<|im_end|>\n"
        f"<|im_start|>assistant\n{{\n"
    )


def translate_audit_for_prompt(report: Dict[str, Any]) -> str:
    """Natural-language summary injected into chat prompts.
    Computed ONCE after inference and stored in audit_store.chat_context."""
    score      = report.get("dpdp_trust_score", 50)
    violations = report.get("violations") or []
    lines      = [f"DPDP Trust Score: {score}/100."]
    if not violations:
        lines.append("Status: Compliant — no critical violations found.")
    else:
        lines.append(f"Found {len(violations)} violation(s):")
        for i, v in enumerate(violations, 1):
            vtype = v.get("violation_type", "Unknown").replace("_", " ")
            ref   = v.get("statute_reference", "N/A")
            ev    = v.get("evidence_quote", "")[:120]
            lines.append(f"{i}. {vtype} (Ref: {ref}) — \"{ev}…\"")
    reasoning = report.get("global_legal_reasoning", "")
    if reasoning:
        lines.append(f"Legal reasoning: {reasoning[:300]}")
    return "\n".join(lines)


def _audit_response(source: str, report: Dict[str, Any], meta: Optional[Dict] = None) -> Dict:
    age_days = meta.get("age_days") if meta else None
    cache_age_hours = round(float(age_days) * 24.0, 1) if age_days is not None else 0.0
    return {
        "source":           source,
        "data":             report,
        "cached_at":        meta.get("cached_at") if meta else None,
        "age_days":         age_days,
        "cache_age_hours":  cache_age_hours,
        "policy_url":       meta.get("policy_url", "") if meta else "",
    }


# ── Audit-chunk concurrency bound (separate from InferenceQueue) ───────────
# _run_inference can fan ONE admitted audit request out to up to
# _audit_max_chunks_for_profile() (default 20 on GPU) concurrent
# generate_audit() calls via asyncio.gather. The InferenceQueue
# (memory_orchestrator.py) only counts REQUESTS, not the individual vLLM
# sequences a request produces internally — so N concurrently-admitted audit
# requests, each fanning out to ~20 chunks, could ask vLLM's scheduler for
# up to N*20 sequences at once. vLLM won't crash (its own scheduler just
# queues what doesn't fit in max_num_seqs), but that burst competes for the
# same batch slots as chat's decode steps, which IS a latency risk for the
# 10k+-concurrent-chat surface this server also has to serve well. This
# semaphore caps the TOTAL number of audit chunk-generations in flight
# across ALL audit requests globally, independent of how many requests the
# InferenceQueue has admitted — leaving the rest of vLLM's max_num_seqs
# budget free for chat. Sized conservatively relative to max_num_seqs (256
# default on GPU) so chat is never starved by an audit burst; raise only if
# you've confirmed audit throughput is the bottleneck for your traffic, not
# chat latency.
_audit_chunk_semaphore: Optional[asyncio.Semaphore] = None


def _get_audit_chunk_semaphore() -> asyncio.Semaphore:
    global _audit_chunk_semaphore
    if _audit_chunk_semaphore is None:
        default_limit = "1" if COMPUTE_PROFILE == "cpu" else "32"
        limit = int(os.getenv("SSENSE_AUDIT_MAX_CONCURRENT_CHUNKS", default_limit))
        _audit_chunk_semaphore = asyncio.Semaphore(limit)
    return _audit_chunk_semaphore


async def _run_inference(domain: str, clean_text: str) -> Dict[str, Any]:
    """Run the audit model across policy chunks and combine into one report.

    Design (matches how the audit LoRA was actually fine-tuned — one policy
    chunk in, one probabilistic score + chain-of-thought out — rather than
    asking it to perform a task shape it never saw in training):

      1. Split the policy into sentence-safe, appropriately-sized chunks
         (chunk_policy_text — unchanged from the previous round: no sentence
         cut in half, small cross-boundary overlap for context).
      2. Run EVERY chunk within the coverage cap through the model
         INDEPENDENTLY and concurrently — each chunk gets its own isolated
         score + reasoning, exactly the input/output shape the model was
         trained on. No chunk's output is shown to the model as input to
         another call.
      3. Discard every chunk that came back clean (dpdp_trust_score == 100,
         no violations) — a clean chunk contributes nothing to the final
         report and including its boilerplate "no issues found" reasoning
         would only dilute the reasoning of the chunks that actually found
         something.
      4. If NO chunk found anything, the policy is clean — return that
         directly, no further processing.
      5. If any chunk scored below 100, deterministically (in Python, NOT
         via another LLM call) merge the violations from every such chunk
         into one congregated violations list, dedup, and recompute a
         combined trust score from the full merged violation set.

    Why no second LLM "consolidation" pass: the audit LoRA adapter was
    fine-tuned specifically for (policy text) -> (score, CoT) — a
    single-chunk, single-pass task. Feeding it a synthetic prompt built from
    its own prior JSON outputs ("here are N sections' findings, reconcile
    them") is a task shape it never saw in training. Greedy decoding
    (temperature=0.0, already the default in engine.py) makes THAT specific
    generation deterministic, but deterministic-and-out-of-distribution is
    still unreliable — it just fails the same way every time instead of
    randomly. A second generative pass was tried in an earlier iteration of
    this pipeline and is deliberately removed: merging is now pure,
    auditable Python logic over model outputs the model actually knows how
    to produce, which also means one less LLM call (and one less unit of
    GPU contention against chat) per multi-chunk audit.
    """
    chunk_size = 1800 if COMPUTE_PROFILE == "cpu" else 3200
    overlap = 1 if COMPUTE_PROFILE == "cpu" else 2
    chunks = chunk_policy_text(clean_text, max_chunk_chars=chunk_size, overlap_sentences=overlap)
    max_eval_chunks = _audit_max_chunks_for_profile()

    if len(chunks) > max_eval_chunks:
        print(f"⚠️  [Audit/Pipeline] {domain}: policy split into {len(chunks)} sections, "
              f"exceeding the {max_eval_chunks}-section cap for the '{COMPUTE_PROFILE}' profile. "
              f"Evaluating the {max_eval_chunks} highest statutory-keyword-density sections; "
              f"{len(chunks) - max_eval_chunks} section(s) will NOT be evaluated this pass. "
              f"Raise SSENSE_AUDIT_MAX_CHUNKS_{'CPU' if COMPUTE_PROFILE == 'cpu' else 'GPU'} "
              f"for full coverage of unusually long policies.")
        selected = select_operative_chunks(chunks, max_chunks=max_eval_chunks)
    else:
        # Common case: full coverage, every section, in original document
        # order — this is what makes the pipeline behave like "the model
        # going through the whole document", not a sampled subset of it.
        selected = list(enumerate(chunks))

    print(f"📊 [Audit/Pipeline] {domain}: {len(clean_text)} chars → {len(chunks)} section(s); evaluating {len(selected)} of them ({'full coverage' if len(selected) == len(chunks) else 'capped'})...")

    semaphore = _get_audit_chunk_semaphore()

    async def _run_one(chunk_text: str) -> Dict[str, Any]:
        prompt = _build_audit_prompt(domain, chunk_text)
        req_id = str(uuid.uuid4())
        async with semaphore:
            raw = await llm_engine.generate_audit(
                request_id=req_id, prompt=prompt, schema=get_dpdp_schema(), max_tokens=1024
            )
        trimmed = raw.strip()
        if not trimmed.startswith("{"):
            trimmed = "{\n" + trimmed
        return validate_and_repair_report(trimmed)

    # Every chunk runs independently and concurrently (bounded by the
    # semaphore above so it can't crowd out chat). vLLM's own continuous
    # batching handles the actual scheduling once admitted.
    # return_exceptions=True: a single chunk error doesn't cancel the other
    # N-1 in-flight vLLM requests (default False would do that).
    raw_results = await asyncio.gather(*[_run_one(text) for _, text in selected], return_exceptions=True)
    chunk_reports = [r for r in raw_results if isinstance(r, dict)]
    chunk_errors  = [r for r in raw_results if isinstance(r, Exception)]
    if chunk_errors:
        print(f"⚠️  [Audit/Pipeline] {domain}: {len(chunk_errors)} chunk(s) errored during generation "
              f"(continuing with {len(chunk_reports)} successful result(s)): {chunk_errors[:2]}")

    if not chunk_reports:
        return {
            "global_legal_reasoning": f"Audit of {domain} could not process policy sections.",
            "violations": [],
            "dpdp_trust_score": 50,
            "subtlety_score": 0,
        }

    # Keep only chunks that found something — "good portions are removed".
    # A chunk counts as flagged if its score is below a clean 100 OR it
    # listed any violation directly; checking both is a defensive
    # cross-check in case the two fields are ever inconsistent in a given
    # generation (they should always agree by construction of the schema,
    # but the merge logic shouldn't silently trust that without checking).
    flagged_reports = [
        r for r in chunk_reports
        if r.get("dpdp_trust_score", 100) < 100 or r.get("violations")
    ]

    print(f"📊 [Audit/Pipeline] {domain}: {len(flagged_reports)}/{len(chunk_reports)} "
          f"section(s) flagged (score < 100 and/or violations found); "
          f"{'congregating their violations' if flagged_reports else 'policy is clean across all evaluated sections'}.")

    if not flagged_reports:
        return {
            "global_legal_reasoning": (
                f"Comprehensive multi-section forensic audit of {domain} under the DPDP Act 2023 "
                "and DPDP Rules 2025 revealed no active statutory contradictions in any of the "
                f"{len(chunk_reports)} operative policy sections evaluated."
            ),
            "violations": [],
            "dpdp_trust_score": 100,
            "subtlety_score": 0,
        }

    # Deterministic congregation of violations from ONLY the flagged
    # sections — pure Python, no further model call. See
    # recombine_audit_reports() for the dedup + severity-scoring logic.
    return recombine_audit_reports(flagged_reports, domain)


@asynccontextmanager
async def _admitted():
    """
    Wraps the actual GPU-bound inference call in the manual admission queue
    (see InferenceQueue in memory_orchestrator.py). Raises HTTPException(503)
    with a Retry-After header — rather than letting QueueSaturatedError
    propagate as a raw 500 — if the wait line is already full or a slot
    never opened up within the configured timeout.
    """
    try:
        await memory_orchestrator.inference_queue.admit()
    except QueueSaturatedError as e:
        raise HTTPException(
            status_code=503,
            detail="Server queue saturated. Retry shortly.",
            headers={"Retry-After": str(e.retry_after)},
        )
    try:
        yield
    finally:
        memory_orchestrator.inference_queue.release()


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    cache_stats = await audit_store.stats()
    q = memory_orchestrator.inference_queue
    return {
        "status":               "online",
        "backend":              getattr(llm_engine, "backend", "vllm"),
        "compute_profile":      COMPUTE_PROFILE,
        "engine_ready":         llm_engine is not None,
        "active_jobs":          q.in_flight,
        "queue_waiting":        q.waiting,
        "max_concurrent":       q.max_concurrent,
        "max_queue":            q.max_waiting,
        "rag_ready":            rag_engine.is_ready,
        "audit_cache":          cache_stats,
        "timestamp":            int(time.time()),
    }


_status_memo: Optional[Dict[str, Any]] = None
_status_memo_time: float = 0.0

@app.get("/v1/status", tags=["Health"])
async def status_probe():
    """
    Lightweight status probe for high-frequency client heartbeats and monitoring.
    Memoized for 5 seconds to support 10k+ concurrent clients without DB/engine overhead.
    """
    global _status_memo, _status_memo_time
    now = time.time()
    if _status_memo and (now - _status_memo_time) < 5.0:
        return _status_memo

    q = memory_orchestrator.inference_queue
    cache_stats = await audit_store.stats()
    _status_memo = {
        "online": True,
        "status": "ready" if (llm_engine is not None) else "starting",
        "cached_domains": cache_stats.get("total_cached_domains", 0),
        "queue_depth": q.waiting,
        "in_flight": q.in_flight,
        "model_loaded": llm_engine is not None,
        "active_sessions": multi_user_session_manager.active_session_count,
        "timestamp": int(now),
    }
    _status_memo_time = now
    return _status_memo


# ── Audit: by URL (primary, preferred) ────────────────────────────────────────
@app.post("/v1/audit/by-url", tags=["Inference"],
          dependencies=[Depends(verify_hmac_signature)])
async def audit_by_url(request: Request, body: AuditByUrlRequest):
    """
    Extension sends {domain, policyUrl}.  Server fetches, extracts, audits.
    Raw policy text is used only during inference and immediately discarded.
    """
    await check_model_extraction_attempt(request, body.policyUrl)

    audit_headers = {
        "X-Ssense-Audit-Remaining": str(getattr(request.state, "audit_remaining", 1000))
    }

    # ── 1. Domain-level cache check ────────────────────────────────────────
    if not body.force_refresh:
        cached = await memory_orchestrator.get_audit_for_domain(body.domain)
        if cached:
            report, meta = cached
            print(f"⚡ [Audit/URL] Domain cache hit: {body.domain} ({meta.get('source')})")
            return JSONResponse(
                content=_audit_response(meta.get("source", "persistent_cache"), report, meta),
                headers=audit_headers,
            )

    # ── Request coalescing: prevent duplicate simultaneous audits for the same domain ──
    is_leader, lease_fut = await memory_orchestrator.acquire_audit_lease(body.domain)
    if not is_leader and not body.force_refresh:
        try:
            print(f"👥 [Audit/URL] Coalescing follower waiting on leader audit for {body.domain}...")
            coalesced_result = await asyncio.wait_for(lease_fut, timeout=180.0)
            return JSONResponse(content=coalesced_result, headers=audit_headers)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"⚠️ [Audit/URL] Follower lease wait failed for {body.domain} ({e}), falling back to independent audit")
            is_leader, lease_fut = await memory_orchestrator.acquire_audit_lease(body.domain)

    try:
        # ── 2. Fetch + extract ─────────────────────────────────────────────────
        fetch: FetchResult = await fetch_policy(body.policyUrl, force=body.force_refresh)
        if not fetch.ok:
            raise HTTPException(422, f"Could not extract policy: {fetch.error}")

        # ── 3. Policy-hash cache check (unchanged policy → same result) ────────
        if not body.force_refresh:
            cached = await memory_orchestrator.get_audit_for_domain(
                body.domain, policy_hash=fetch.policy_hash
            )
            if cached:
                report, meta = cached
                print(f"⚡ [Audit/URL] Hash match: {body.domain}")
                resp_data = _audit_response("persistent_cache:hash_match", report, meta)
                if is_leader:
                    await memory_orchestrator.complete_audit_lease(body.domain, result=resp_data)
                return JSONResponse(content=resp_data, headers=audit_headers)

        # ── 4. Inference ───────────────────────────────────────────────────────
        if llm_engine is None:
            raise HTTPException(503, "SLM engine is still initializing. Please wait a few moments.")
        async with _admitted():
            clean_text = sanitize_input_prompt(fetch.text, is_audit_policy=True)
            report     = await _run_inference(body.domain, clean_text)

            # !! Policy text is discarded here — never written to DB or returned !!
            del clean_text

            chat_ctx   = translate_audit_for_prompt(report)
            await memory_orchestrator.save_audit(
                body.domain, fetch.policy_hash, report, chat_ctx, fetch.policy_url
            )
            resp_data = _audit_response("inference", report,
                                        {"policy_url": fetch.policy_url, "cached_at": int(time.time()), "age_days": 0})
            if is_leader:
                await memory_orchestrator.complete_audit_lease(body.domain, result=resp_data)
            return JSONResponse(content=resp_data, headers=audit_headers)
    except BaseException as exc:
        if is_leader:
            await memory_orchestrator.complete_audit_lease(body.domain, error=exc)
        raise


# ── Audit: by text (legacy — extension pre-extracted) ─────────────────────────
@app.post("/v1/audit", tags=["Inference"],
          dependencies=[Depends(verify_hmac_signature)])
async def audit_by_text(request: Request, body: AuditByTextRequest):
    """
    Legacy endpoint: extension sends extracted policy text.
    Delegates to the same cache + inference path as /v1/audit/by-url.
    Text is sanitised, hashed, used for inference, then discarded.
    """
    clean_text = sanitize_input_prompt(body.policyText, is_audit_policy=True)
    await check_model_extraction_attempt(request, clean_text)

    import hashlib
    policy_hash = hashlib.sha256(clean_text.encode()).hexdigest()

    if not body.force_refresh:
        cached = await memory_orchestrator.get_audit_for_domain(
            body.domain, policy_hash=policy_hash
        )
        if cached:
            report, meta = cached
            del clean_text
            return _audit_response(meta.get("source", "persistent_cache"), report, meta)

    if llm_engine is None:
        raise HTTPException(503, "SLM engine is still initializing. Please wait a few moments.")
    async with _admitted():
        report   = await _run_inference(body.domain, clean_text)
        del clean_text
        chat_ctx = translate_audit_for_prompt(report)
        await memory_orchestrator.save_audit(body.domain, policy_hash, report, chat_ctx)
        return _audit_response("inference", report)


# ── Audit: GET cached ──────────────────────────────────────────────────────────
@app.get("/v1/audit/{domain}", tags=["Inference"],
         dependencies=[Depends(verify_hmac_signature)])
async def get_cached_audit(domain: str):
    cached = await memory_orchestrator.get_audit_for_domain(domain)
    if not cached:
        raise HTTPException(404, f"No cached audit for '{domain}'.")
    report, meta = cached
    return _audit_response(meta.get("source", "persistent_cache"), report, meta)


# ── Audit: force refresh ───────────────────────────────────────────────────────
@app.post("/v1/audit/{domain}/refresh", tags=["Inference"],
          dependencies=[Depends(verify_hmac_signature)])
async def refresh_audit(request: Request, domain: str, body: AuditByUrlRequest):
    # BUG FIX: this used to call `audit_by_url(body)`, silently binding `body`
    # to `audit_by_url`'s `request` parameter and leaving `body` unfilled -
    # every call raised "missing 1 required positional argument: 'body'".
    body.domain        = domain
    body.force_refresh = True
    return await audit_by_url(request, body)


# ── Chat: SSE stream (rate-limited) ───────────────────────────────────────────
@app.post("/v1/chat/stream", tags=["Inference"],
          dependencies=[Depends(verify_hmac_signature_chat)])
async def chat(request: Request, body: ChatRequest):
    """
    RAG-augmented SSE chat.
    Gate: requires a completed audit for the domain.
    Rate limit: 60 req/min per (api_key + IP). Audits are unlimited.
    Chat context read from pre-computed audit_store.chat_context — no JSON
    parsing on this hot path.
    """
    if llm_engine is None:
        raise HTTPException(503, "SLM engine is still initializing. Please wait a few moments.")
    user_header = request.headers.get("X-Ssense-User-Id", "")
    api_key = request.headers.get("X-Ssense-API-Key", "")
    user_id = f"{api_key}:{user_header}" if user_header else f"{api_key}:{get_client_ip(request)}"

    # Rate limits are pre-enforced in verify_hmac_signature_chat dependency.
    # Retrieve remaining quota recorded on request.state to avoid double-counting.
    remaining = getattr(request.state, "chat_remaining_min", None)
    daily_rem = getattr(request.state, "chat_remaining_day", None)
    daily_reset = getattr(request.state, "chat_reset_day", 86400)

    if remaining is None or daily_rem is None:
        client_id = f"chat:{user_id}"
        limited, remaining = await memory_orchestrator.enforce_chat_rate_limit(client_id)
        daily_limited, daily_rem, daily_reset = await memory_orchestrator.enforce_daily_chat_rate_limit(client_id)
        if limited:
            raise HTTPException(
                429,
                "Chat rate limit exceeded (60 req/min). Audit is unlimited.",
                headers={"Retry-After": "60", "X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0"},
            )
        if daily_limited:
            raise HTTPException(
                429,
                "Daily chat quota exceeded (200 req/day per user). Resets tomorrow. Audit is unlimited.",
                headers={"Retry-After": str(daily_reset), "X-DailyLimit-Limit": "200", "X-DailyLimit-Remaining": "0", "X-DailyLimit-Reset": str(daily_reset)},
            )

    rate_limit_headers = {
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Window": "60",
        "X-DailyLimit-Limit": "200",
        "X-DailyLimit-Remaining": str(max(0, daily_rem)),
        "X-DailyLimit-Reset": str(daily_reset),
    }

    clean_prompt = sanitize_input_prompt(body.userPrompt, is_audit_policy=False)
    await check_model_extraction_attempt(request, clean_prompt)
    mode       = "thinking" if body.responseMode == "thinking" else "concise"
    max_tokens = CHAT_MAX_TOKENS_THINKING if mode == "thinking" else CHAT_MAX_TOKENS_CONCISE

    # ── Audit gate (reads pre-computed context for current site + mentioned domains) ─
    audited_contexts, unaudited_domains = await memory_orchestrator.resolve_mentioned_domains(
        clean_prompt, current_domain=body.domain
    )
    if not audited_contexts:
        async def _gate():
            yield f"data: {json.dumps({'event':'token','data':'Please run an Audit on this site (or mention an audited site) before chatting.'})}\n\n"
            yield f"data: {json.dumps({'event':'done'})}\n\n"
        return StreamingResponse(_gate(), media_type="text/event-stream", headers=rate_limit_headers)

    # Format multi-site audit summaries into system prompt
    audit_blocks = [
        f"[AUDIT SUMMARY FOR {d}]\n{ctx}" for d, ctx in audited_contexts.items()
    ]
    for d in unaudited_domains:
        audit_blocks.append(f"[AUDIT STATUS FOR {d}]\nNot yet audited in Ssense.")
    all_audit_context_str = "\n\n".join(audit_blocks)

    # ── Request coalescing ─────────────────────────────────────────────────
    task_key = memory_orchestrator.compute_sha256(
        f"chat::{mode}::{body.domain}::{clean_prompt}", "chat"
    )
    is_leader, broadcaster = await memory_orchestrator.acquire_execution_lease(task_key)

    if not is_leader:
        async def _coalesced():
            q = broadcaster.subscribe()
            while True:
                item = await q.get()
                if item is None:
                    break
                event, data = item
                yield f"data: {json.dumps({'event': event, 'data': data})}\n\n"
        return StreamingResponse(_coalesced(), media_type="text/event-stream", headers=rate_limit_headers)

    # ── Leader: admit into the bounded inference queue, then RAG + generate ─
    length_instr = (
        "Think step by step through the DPDP provisions. A thorough, well-reasoned answer is expected."
        if mode == "thinking"
        else "Answer in 2-4 sentences. Be direct and skip preamble."
    )

    async def _primary():
        try:
            try:
                await memory_orchestrator.inference_queue.admit()
            except QueueSaturatedError as e:
                # Followers subscribed to this task_key are waiting on this
                # exact broadcaster — without this emit() they'd hang until
                # their own client-side timeout instead of failing fast.
                await broadcaster.emit("error", f"Server queue saturated. Retry in ~{e.retry_after}s.")
                yield f"data: {json.dumps({'event':'error','data':f'Server queue saturated. Retry in ~{e.retry_after}s.'})}\n\n"
                return

            try:
                rag_k = 1 if COMPUTE_PROFILE == "cpu" else 3
                context_str, hits = await rag_engine.retrieve_context(clean_prompt, top_k=rag_k)
                citations = [h["metadata"] for h in hits]

                # Conditionally prepend [STATUTORY CONTEXT] block.
                # When retrieve_context returns "" (no confident hits), omit it
                # entirely — the model was trained to produce RAFT refusal phrases
                # when context is absent, not to hallucinate from XML stubs.
                if len(audited_contexts) == 1 and body.domain in audited_contexts:
                    target_label = body.domain
                else:
                    target_label = ", ".join(audited_contexts.keys())

                user_content = (
                    f"{context_str}\n\nQuestion about {target_label}: {clean_prompt}"
                    if context_str
                    else f"Question about {target_label}: {clean_prompt}"
                )

                # Multi-turn history injection
                session_domain = body.domain if (body.domain and body.domain not in ("newtab", "blank", "localhost")) else list(audited_contexts.keys())[0]
                history_prompt = await multi_user_session_manager.get_history_prompt(user_id, session_domain)
                history_block = f"\n{history_prompt}" if history_prompt else ""

                prompt = (
                    "<|im_start|>system\nYou are the Ssense DPDP Co-Pilot. "
                    "Ground ALL answers in the retrieved context and audit report.\n"
                    f"RESPONSE LENGTH: {length_instr}\n\n"
                    f"{all_audit_context_str}<|im_end|>{history_block}\n"
                    f"<|im_start|>user\n{user_content}<|im_end|>\n"
                    "<|im_start|>assistant\n"
                )

                await broadcaster.emit("citations", citations)
                yield f"data: {json.dumps({'event':'citations','data':citations})}\n\n"

                req_id = str(uuid.uuid4())
                generated_tokens = []
                async for tok in llm_engine.generate_chat_stream(req_id, prompt, max_tokens=max_tokens):
                    generated_tokens.append(tok)
                    await broadcaster.emit("token", tok)
                    yield f"data: {json.dumps({'event':'token','data':tok})}\n\n"

                if generated_tokens:
                    await multi_user_session_manager.record_turn(
                        user_id, session_domain, clean_prompt, "".join(generated_tokens)
                    )
            finally:
                memory_orchestrator.inference_queue.release()

            await broadcaster.emit("done")
            yield f"data: {json.dumps({'event':'done'})}\n\n"
        finally:
            await memory_orchestrator.cleanup_stream(task_key, broadcaster)

    return StreamingResponse(_primary(), media_type="text/event-stream", headers=rate_limit_headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1, log_level="info", lifespan="on")
