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
from fastapi.responses import StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded

from audit_store import audit_store
from engine import ProductionAsyncEngine, detect_hardware_capabilities
from memory_orchestrator import memory_orchestrator, QueueSaturatedError
from policy_fetcher import fetch_policy, FetchResult
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
    models_dir      = Path(os.getenv("MODELS_DIR", "/app/models"))
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
    print("✅ Ssense SLM Server ready.")
    yield
    print("🛑 Shutting down...")
    await audit_store.close()


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
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Window", "Retry-After"],
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


def chunk_policy_text(text: str, max_chunk_chars: int = 3200) -> list[str]:
    """Splits policy text into coherent paragraph-aware segments of at most max_chunk_chars."""
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]

    # If any individual paragraph exceeds max_chunk_chars, subdivide it
    normalized_paragraphs: list[str] = []
    for p in paragraphs:
        if len(p) <= max_chunk_chars:
            normalized_paragraphs.append(p)
        else:
            sub_parts = re.split(r'(?<=[.!?])\s+', p)
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

    chunks = []
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
    return chunks


def select_operative_chunks(chunks: list[str], max_chunks: int = 2) -> list[tuple[int, str]]:
    """Scores chunks by statutory legal clause density and selects top operative windows."""
    if len(chunks) <= max_chunks:
        return list(enumerate(chunks))

    scored = []
    for idx, c in enumerate(chunks):
        coverage = sum(1 for pat in _DPDP_KEYWORD_PATTERNS.values() if pat.search(c))
        density = sum(len(pat.findall(c)) for pat in _DPDP_KEYWORD_PATTERNS.values())
        score = coverage * 10 + min(density, 20)
        scored.append((idx, score, c))

    scored.sort(key=lambda x: x[1], reverse=True)
    selected = [scored[0]]
    for item in scored[1:]:
        if len(selected) >= max_chunks:
            break
        selected.append(item)

    selected.sort(key=lambda x: x[0])
    return [(idx, c) for idx, _, c in selected]


def recombine_audit_reports(chunk_reports: list[Dict[str, Any]], domain: str) -> Dict[str, Any]:
    """Fuses multi-chunk forensic audit outputs into a single deduplicated,
    statistically calibrated DPDP audit report."""
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
        dpdp_trust_score = 95
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
    policy_slice = clean_text[:3200].strip()
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
    return {
        "source":    source,
        "data":      report,
        "cached_at": meta.get("cached_at") if meta else None,
        "age_days":  meta.get("age_days")  if meta else None,
        "policy_url":meta.get("policy_url","") if meta else "",
    }


async def _run_inference(domain: str, clean_text: str) -> Dict[str, Any]:
    """Run the audit LLM across operative policy chunks and recombine into a cohesive report."""
    chunks = chunk_policy_text(clean_text, max_chunk_chars=3200)
    max_eval_chunks = 2 if COMPUTE_PROFILE == "cpu" else 4
    selected = select_operative_chunks(chunks, max_chunks=max_eval_chunks)

    print(f"📊 [Audit/Pipeline] Divided {len(clean_text)} chars into {len(chunks)} chunks; evaluating top {len(selected)} operative chunk(s)...")

    chunk_reports = []
    for chunk_idx, chunk_text in selected:
        prompt = _build_audit_prompt(domain, chunk_text)
        req_id = str(uuid.uuid4())
        raw = await llm_engine.generate_audit(
            request_id=req_id, prompt=prompt, schema=get_dpdp_schema(), max_tokens=1024
        )
        trimmed = raw.strip()
        if not trimmed.startswith("{"):
            trimmed = "{\n" + trimmed
        validated = validate_and_repair_report(trimmed)
        chunk_reports.append(validated)

    if len(chunk_reports) == 1:
        return chunk_reports[0]

    return recombine_audit_reports(chunk_reports, domain)


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


# ── Audit: by URL (primary, preferred) ────────────────────────────────────────
@app.post("/v1/audit/by-url", tags=["Inference"],
          dependencies=[Depends(verify_hmac_signature)])
async def audit_by_url(request: Request, body: AuditByUrlRequest):
    """
    Extension sends {domain, policyUrl}.  Server fetches, extracts, audits.
    Raw policy text is used only during inference and immediately discarded.
    """
    await check_model_extraction_attempt(request, body.policyUrl)

    # ── 1. Domain-level cache check ────────────────────────────────────────
    if not body.force_refresh:
        cached = await memory_orchestrator.get_audit_for_domain(body.domain)
        if cached:
            report, meta = cached
            print(f"⚡ [Audit/URL] Domain cache hit: {body.domain} ({meta.get('source')})")
            return _audit_response(meta.get("source", "persistent_cache"), report, meta)

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
            return _audit_response("persistent_cache:hash_match", report, meta)

    # ── 4. Inference ───────────────────────────────────────────────────────
    async with _admitted():
        clean_text = sanitize_input_prompt(fetch.text, is_audit_policy=True)
        report     = await _run_inference(body.domain, clean_text)

        # !! Policy text is discarded here — never written to DB or returned !!
        del clean_text

        chat_ctx   = translate_audit_for_prompt(report)
        await memory_orchestrator.save_audit(
            body.domain, fetch.policy_hash, report, chat_ctx, fetch.policy_url
        )
        return _audit_response("inference", report,
                               {"policy_url": fetch.policy_url, "cached_at": int(time.time()), "age_days": 0})


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
    user_id = f"{request.headers.get('X-Ssense-API-Key','')}:{get_client_ip(request)}"
    limited, remaining = await memory_orchestrator.enforce_chat_rate_limit(user_id)
    rate_limit_headers = {
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Window": "60",
    }
    if limited:
        # Audits are never rate-limited — only chat. Retry-After is a flat
        # 60s (the window size) since the sliding window means the exact
        # next-available-slot time isn't a single fixed instant.
        raise HTTPException(
            429,
            "Chat rate limit exceeded (60 req/min). Audit is unlimited.",
            headers={**rate_limit_headers, "Retry-After": "60"},
        )

    clean_prompt = sanitize_input_prompt(body.userPrompt, is_audit_policy=False)
    await check_model_extraction_attempt(request, clean_prompt)
    mode       = "thinking" if body.responseMode == "thinking" else "concise"
    max_tokens = CHAT_MAX_TOKENS_THINKING if mode == "thinking" else CHAT_MAX_TOKENS_CONCISE

    # ── Audit gate (fast: reads pre-computed context string) ───────────────
    chat_context = await memory_orchestrator.get_chat_context(body.domain)
    if chat_context is None:
        async def _gate():
            yield f"data: {json.dumps({'event':'token','data':'Please run an Audit on this site before chatting.'})}\n\n"
            yield f"data: {json.dumps({'event':'done'})}\n\n"
        return StreamingResponse(_gate(), media_type="text/event-stream", headers=rate_limit_headers)

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
                context_str, hits = await rag_engine.retrieve_context(clean_prompt, top_k=3)
                citations = [h["metadata"] for h in hits]

                # Conditionally prepend [STATUTORY CONTEXT] block.
                # When retrieve_context returns "" (no confident hits), omit it
                # entirely — the model was trained to produce RAFT refusal phrases
                # when context is absent, not to hallucinate from XML stubs.
                user_content = (
                    f"{context_str}\n\nQuestion about {body.domain}: {clean_prompt}"
                    if context_str
                    else f"Question about {body.domain}: {clean_prompt}"
                )

                prompt = (
                    "<|im_start|>system\nYou are the Ssense DPDP Co-Pilot. "
                    "Ground ALL answers in the retrieved context and audit report.\n"
                    f"RESPONSE LENGTH: {length_instr}\n\n"
                    f"[AUDIT SUMMARY FOR {body.domain}]\n{chat_context}<|im_end|>\n"
                    f"<|im_start|>user\n{user_content}<|im_end|>\n"
                    "<|im_start|>assistant\n"
                )

                await broadcaster.emit("citations", citations)
                yield f"data: {json.dumps({'event':'citations','data':citations})}\n\n"

                req_id = str(uuid.uuid4())
                async for tok in llm_engine.generate_chat_stream(req_id, prompt, max_tokens=max_tokens):
                    await broadcaster.emit("token", tok)
                    yield f"data: {json.dumps({'event':'token','data':tok})}\n\n"
            finally:
                memory_orchestrator.inference_queue.release()

            await broadcaster.emit("done")
            yield f"data: {json.dumps({'event':'done'})}\n\n"
        finally:
            await memory_orchestrator.cleanup_stream(task_key, broadcaster)

    return StreamingResponse(_primary(), media_type="text/event-stream", headers=rate_limit_headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1, log_level="info")
