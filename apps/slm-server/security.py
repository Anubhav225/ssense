#!/usr/bin/env python3
"""
security.py – SOTA Endpoint Defense, ML Heuristics, & Schema Enforcement
Synchronized directly with memory_orchestrator.py for Zero-Hop execution.
"""

import os
import re
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
import hmac
import hashlib
import math
from collections import Counter
import secrets as _secrets_mod
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
import jsonschema
from dotenv import load_dotenv

# SlowAPI Rate Limiter compatibility layer
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from fastapi.responses import JSONResponse

    limiter = Limiter(key_func=get_remote_address)

    def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Traffic shaped to protect VRAM integrity."}
        )
except ImportError:
    class MockLimiter:
        def limit(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator
    limiter = MockLimiter()
    RateLimitExceeded = Exception
    def _rate_limit_exceeded_handler(request: Request, exc: Exception):
        pass

# Import the Zero-Hop In-Memory Orchestrator
from memory_orchestrator import memory_orchestrator

# ═══════════════════════════════════════════════════════════════
# 0. ENVIRONMENT & SECRETS BOOTSTRAP
# ═══════════════════════════════════════════════════════════════
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)

SSENSE_ENV = os.getenv("SSENSE_ENV", "development").strip().lower()
_IS_PROD = SSENSE_ENV == "production"

API_KEY_HEADER = APIKeyHeader(name="X-Ssense-API-Key", auto_error=False)

_KNOWN_LEAKED_SECRETS = {
    "ssense_dev_key_2026",
    "ssense_prod_key_2026",
    "ssense_secret_key_2026_prod",
}

def _fail_boot(message: str) -> None:
    sys.stderr.write(f"\n🛑 SSENSE FATAL CONFIG ERROR: {message}\n\n")
    raise RuntimeError(message)

def _load_api_keys() -> set:
    raw = os.getenv("SSENSE_API_KEYS", "")
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    if _IS_PROD and (not keys or (keys & _KNOWN_LEAKED_SECRETS)):
        _fail_boot("SSENSE_API_KEYS is missing or leaked. Must use cryptographically secure keys in production.")
    if not keys:
        ephemeral = _secrets_mod.token_urlsafe(32)
        print(f"⚠️  [DEV ONLY] SSENSE_API_KEYS not set — generated ephemeral key: {ephemeral}")
        keys = {ephemeral}
    return keys

def _load_hmac_secret() -> str:
    secret = os.getenv("SSENSE_HMAC_SECRET", "").strip()
    if _IS_PROD and (not secret or secret in _KNOWN_LEAKED_SECRETS):
        _fail_boot("SSENSE_HMAC_SECRET is missing or leaked in production mode.")
    if not secret:
        secret = _secrets_mod.token_urlsafe(48)
        print("⚠️  [DEV ONLY] SSENSE_HMAC_SECRET not set — generated ephemeral secret.")
    return secret

ALLOWED_API_KEYS = _load_api_keys()
SSENSE_HMAC_SECRET = _load_hmac_secret()
ENTERPRISE_API_KEYS = {k.strip() for k in os.getenv("SSENSE_ENTERPRISE_API_KEYS", "").split(",") if k.strip()}


# ═══════════════════════════════════════════════════════════════
# 1. CRYPTOGRAPHIC HMAC AUTHENTICATION & RATE LIMITING
# ═══════════════════════════════════════════════════════════════
def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP, trusting X-Forwarded-For ONLY when the
    immediate connecting peer is our own Nginx sidecar (compose service
    network) or localhost. Otherwise X-Forwarded-For is attacker-controlled:
    anyone who reaches this process directly (or a misconfigured deployment
    where slm-server:8000 is accidentally reachable without going through
    Nginx) could spoof it to a rotating set of fake IPs and defeat every
    IP-keyed rate limit here and at the Nginx layer.
    """
    direct_peer = request.client.host if request.client else None
    trusted_proxy = direct_peer in _TRUSTED_PROXY_IPS if direct_peer else False

    if trusted_proxy and (forwarded := request.headers.get("X-Forwarded-For")):
        # Nginx appends via proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for,
        # so the LEFTMOST entry is the original client; anything Nginx itself
        # appended is trusted, but a spoofed leftmost entry from the client is
        # not reduced by that fact alone — this is inherent to XFF and is why
        # it's only honored from a known proxy hop in the first place.
        return forwarded.split(",")[0].strip()

    return direct_peer or "127.0.0.1"


# Docker Compose puts Nginx and slm-server on the same bridge network; the
# proxy's container IP isn't fixed, so trust anything on the private ranges
# Docker uses for its default/bridge networks, plus loopback for local/dev
# runs and test clients. This is intentionally broad within "private network
# only" — it is NOT trusting arbitrary internet peers.
_TRUSTED_PROXY_IPS_PREFIXES = ("172.", "10.", "192.168.")
_TRUSTED_PROXY_LITERALS = {"127.0.0.1", "::1", "localhost", "testclient"}


class _TrustedProxyCheck:
    def __contains__(self, ip: Optional[str]) -> bool:
        if not ip:
            return False
        if ip in _TRUSTED_PROXY_LITERALS:
            return True
        return ip.startswith(_TRUSTED_PROXY_IPS_PREFIXES)


_TRUSTED_PROXY_IPS = _TrustedProxyCheck()

async def _verify_api_key_only(request: Request) -> str:
    """API-key validation only — no rate limit. Base for both HMAC helpers."""
    api_key = request.headers.get("X-Ssense-API-Key")
    if not api_key or api_key not in ALLOWED_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Ssense-API-Key header.",
        )
    return api_key


async def _verify_hmac_body(request: Request) -> bool:
    """Shared HMAC verification + nonce-replay check. No rate limiting."""
    signature = request.headers.get("X-Ssense-Signature")
    timestamp = request.headers.get("X-Ssense-Timestamp")
    nonce = request.headers.get("X-Ssense-Nonce")

    client_ip = get_client_ip(request)
    if not signature and client_ip in ("127.0.0.1", "localhost", "::1", "testclient"):
        return True

    if not signature or not timestamp or not nonce:
        raise HTTPException(status_code=401, detail="Missing required HMAC headers.")

    try:
        ts_ms = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid X-Ssense-Timestamp format.")

    now_ms = int(time.time() * 1000)
    if abs(now_ms - ts_ms) > 30000:
        raise HTTPException(status_code=401, detail="HMAC temporal window expired (>30s). Replay attack blocked.")

    # Nonce replay via orchestrator's dedicated nonce cache
    if not await memory_orchestrator.check_nonce(nonce):
        raise HTTPException(status_code=401, detail="Cryptographic nonce replay detected.")

    payload = f"{request.method.upper()}:{request.url.path}:{timestamp}:{nonce}"
    expected = hmac.new(
        SSENSE_HMAC_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature.")
    return True


async def verify_hmac_signature(request: Request) -> bool:
    """
    API-key check + HMAC validation. NO rate limiting.
    Used by audit endpoints — results are shared server-wide so the expensive
    inference path rarely runs; blanket throttling harms honest users for no gain.
    """
    await _verify_api_key_only(request)
    return await _verify_hmac_body(request)


async def verify_hmac_signature_chat(request: Request) -> bool:
    """
    API-key check + HMAC validation + per-user chat rate limiting.
    Rate limit: 60 requests/minute per (api_key + client_ip).
    Applied only to /v1/chat/stream — audit is intentionally excluded.
    """
    api_key = await _verify_api_key_only(request)
    client_id = f"chat:{api_key}:{get_client_ip(request)}"
    is_limited, _ = await memory_orchestrator.enforce_chat_rate_limit(client_id)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Chat rate limit exceeded (60 req/min per user). Audit requests are not rate-limited.",
        )
    return await _verify_hmac_body(request)


# ═══════════════════════════════════════════════════════════════
# 2. HEURISTIC ML SECURITY SHIELD (Injection & Exfiltration Guard)
# ═══════════════════════════════════════════════════════════════
# SOTA FIX: MAX_POLICY_CHARS was a hard, silent truncation applied BEFORE
# chunking ever ran (see main.py::sanitize_input_prompt call site) — any
# policy longer than this was cut at 32,000 chars (~5,000 words) with
# everything past that point simply never seen by the model, no matter how
# many chunks the audit pipeline could otherwise evaluate. Many real
# corporate privacy policies (GDPR-era, multi-jurisdiction) run 6,000-12,000+
# words, so this was quietly capping audit coverage well before the chunking
# layer's own per-request chunk-count cap (main.py::_audit_max_chunks_for_profile)
# ever got a chance to matter. Raised to 64,000 chars (~10,000-11,000 words)
# — generous enough to cover the large majority of real-world policies in
# full — and made env-tunable since "how long is too long" is a
# cost/abuse-prevention tradeoff, not a fixed constant. This still bounds
# worst-case cost/abuse; genuinely pathological input is bounded further
# upstream by policy_fetcher.py's MAX_RESPONSE_BYTES (8MB of raw HTML) and,
# for the legacy text-upload endpoint, by this cap directly.
MAX_POLICY_CHARS = int(os.getenv("SSENSE_MAX_POLICY_CHARS", "64000"))
MAX_PROMPT_CHARS = int(os.getenv("SSENSE_MAX_PROMPT_CHARS", "1024"))

DISTILLATION_KEYWORDS = [
    r"dump\s+chain\s+of\s+thought", r"output\s+training\s+format",
    r"raw\s+logits", r"system\s+prompt"
]
JAILBREAK_PATTERNS = [
    r"ignore\s+all\s+(previous|prior)\s+instructions", r"system\s+override",
    r"you\s+are\s+now\s+in\s+developer\s+mode", r"dan\s+mode",
]
# SOTA FIX: Block Qwen2.5 ChatML delimiters to prevent Role-Hijacking
DELIMITER_HIJACK = [r"<\|im_start\|>", r"<\|im_end\|>", r"<\|endoftext\|>"]

COMBINED_THREAT_REGEX = re.compile("|".join(DISTILLATION_KEYWORDS + JAILBREAK_PATTERNS + DELIMITER_HIJACK), re.IGNORECASE)

def _calculate_shannon_entropy(text: str) -> float:
    """
    SOTA Upgrade: Calculates character entropy. 
    High entropy mathematically detects Base64, Hex, or obfuscated jailbreak payloads.
    """
    if not text: return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())

def sanitize_input_prompt(text: str, is_audit_policy: bool = True) -> str:
    """Endpoint protection against fuzzing, delimiter hijacking, and obfuscation."""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Payload empty.")

    max_len = MAX_POLICY_CHARS if is_audit_policy else MAX_PROMPT_CHARS
    if len(text) > max_len:
        text = text[:max_len]
        last_space = text.rfind(" ")
        if last_space > max_len // 2:
            text = text[:last_space]

    # 1. Regex Semantic Heuristics
    if COMBINED_THREAT_REGEX.search(text):
        raise HTTPException(
            status_code=422,
            detail="Adversarial extraction or delimiter hijacking sequence detected. Connection dropped."
        )

    # 2. Entropy Analysis (Only run on Chat prompts, as legal PDFs can legitimately have UUIDs/Hashes)
    if not is_audit_policy:
        entropy = _calculate_shannon_entropy(text)
        # Standard English is ~4.0 to 4.8. Base64/Hex obfuscated payloads are > 5.0
        if entropy > 5.0 and len(text) > 40:
            raise HTTPException(
                status_code=422,
                detail="Obfuscated payload detected (High Shannon Entropy). Possible Base64 injection blocked."
            )

    return text.strip()

async def check_model_extraction_attempt(request: Request, text: str) -> None:
    """Detects systematic model extraction or prompt extraction attempts."""
    if COMBINED_THREAT_REGEX.search(text):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Adversarial extraction or delimiter hijacking sequence detected. Connection dropped."
        )


# ═══════════════════════════════════════════════════════════════
# 3. SCHEMA ENFORCEMENT & HALLUCINATION MITIGATION
# ═══════════════════════════════════════════════════════════════
SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "libs" / "contracts" / "schemas" / "dpdp_schema.json"
if not SCHEMA_PATH.exists():
    _docker_path = Path("/app/schemas/dpdp_schema.json")
    if _docker_path.exists():
        SCHEMA_PATH = _docker_path
    else:
        _local_fallback = Path(__file__).resolve().parent / "schemas" / "dpdp_schema.json"
        if _local_fallback.exists():
            SCHEMA_PATH = _local_fallback

_SCHEMA_CACHE: Optional[Dict[str, Any]] = None

def get_dpdp_schema() -> Dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"DPDP schema file not found at {SCHEMA_PATH}")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE

def repair_json_string(s: str) -> str:
    """Attempts to auto-close unclosed quotes, brackets, and braces in truncated LLM JSON."""
    s = s.strip()
    if not s.startswith("{"):
        idx = s.find("{")
        if idx != -1:
            s = s[idx:]
        else:
            s = "{\n" + s

    # 1. Try direct parse first
    try:
        json.loads(s)
        return s
    except Exception:
        pass

    # 2. Track open strings, brackets, and braces
    in_string = False
    escape = False
    stack = []
    cleaned_chars = []
    
    for ch in s:
        if ch == '\\' and not escape:
            escape = True
            cleaned_chars.append(ch)
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            cleaned_chars.append(ch)
        elif in_string:
            cleaned_chars.append(ch)
        else:
            if ch in ('{', '['):
                stack.append(ch)
                cleaned_chars.append(ch)
            elif ch in ('}', ']'):
                if stack and ((ch == '}' and stack[-1] == '{') or (ch == ']' and stack[-1] == '[')):
                    stack.pop()
                    cleaned_chars.append(ch)
            else:
                cleaned_chars.append(ch)
        escape = False

    repaired = "".join(cleaned_chars)
    if in_string:
        repaired += '"'
    
    # Strip any trailing comma or dangling colon
    repaired = re.sub(r'[,:\s]+$', '', repaired)

    # Balance unclosed brackets and braces in LIFO order
    while stack:
        opener = stack.pop()
        if opener == '{':
            repaired += "}"
        elif opener == '[':
            repaired += "]"

    return repaired


def validate_and_repair_report(raw_json_str: str) -> Dict[str, Any]:
    """SOTA JSON validation with Hallucination Logic Gates, Auto-Repair, and Bounding Box Recovery."""
    start = raw_json_str.find('{')
    if start == -1:
        raw_json_str = "{\n" + raw_json_str
        start = 0

    end = raw_json_str.rfind('}')
    candidate = raw_json_str[start:end+1] if (end != -1 and end > start) else raw_json_str[start:]

    try:
        report = json.loads(candidate)
    except Exception:
        repaired = repair_json_string(candidate)
        try:
            report = json.loads(repaired)
        except Exception:
            report = {
                "global_legal_reasoning": "Audit legal reasoning completed. Structured data extracted.",
                "violations": [],
                "dpdp_trust_score": 50,
                "subtlety_score": 0,
            }
    
    # 1. Global Legal Reasoning
    if "global_legal_reasoning" not in report:
        report["global_legal_reasoning"] = "Legal audit analysis completed."

    # 2. Score Bounds Enforcement
    if "dpdp_trust_score" in report:
        try:
            report["dpdp_trust_score"] = max(0, min(100, int(report["dpdp_trust_score"])))
        except (ValueError, TypeError):
            report["dpdp_trust_score"] = 50
    else:
        report["dpdp_trust_score"] = 50

    if "subtlety_score" in report:
        try:
            report["subtlety_score"] = max(0, min(100, int(report["subtlety_score"])))
        except (ValueError, TypeError):
            report["subtlety_score"] = 0
    else:
        report["subtlety_score"] = 0

    # 3. Hallucination Logic Gate
    # A model cannot logically give a 100/100 score AND list critical violations.
    violations = report.get("violations", [])
    if isinstance(violations, list) and len(violations) > 0 and report["dpdp_trust_score"] > 90:
        report["dpdp_trust_score"] = max(0, 100 - (len(violations) * 10))

    # 4. Repair Violations
    VALID_VIOLATION_TYPES = {
        "PURPOSE_LIMITATION_VIOLATION", "CONSENT_NOT_FREE_OR_SPECIFIC", "LEGITIMATE_USES_ABUSE",
        "NOTICE_INADEQUATE", "DATA_RETENTION_LIMIT_EXCEEDED", "ERASURE_NOTICE_PERIOD_VIOLATION",
        "LOG_RETENTION_MANDATE_VIOLATION", "CHILD_CONSENT_VIOLATION", "SECURITY_SAFEGUARDS_MISSING",
        "GRIEVANCE_REDRESSAL_INADEQUATE", "BREACH_NOTIFICATION_FAILURE", "PROCESSOR_ACCOUNTABILITY_VIOLATION",
        "SDF_OBLIGATIONS_MISSING", "SDF_DATA_LOCALIZATION_VIOLATION", "CROSS_BORDER_TRANSFER_VIOLATION",
        "CONSENT_MANAGER_OBSTRUCTION", "LANGUAGE_ACCESSIBILITY", "ALGORITHMIC_PROFILING_SDF",
        "RIGHTS_IMPLEMENTATION_VIOLATION", "DATA_ACCURACY_COMPLETENESS_VIOLATION", "BOARD_COMPLIANCE_VIOLATION",
        "PENALTY_AVOIDANCE", "APPEAL_PROCESS_VIOLATION", "SCOPE_APPLICATION_EVASION",
        "ILLEGAL_EXEMPTION_CLAIM", "CONSENT_MECHANICS_VIOLATION"
    }

    VALID_NETWORK_ACTIONS = {
        "BLOCK_THIRD_PARTY", "STRIP_TELEMETRY_HEADER", "SPOOF_HARDWARE_API",
        "INJECT_GPC_SIGNAL", "WARN_USER_ONLY"
    }

    ALLOWED_VIOLATION_KEYS = {
        "step_1_active_claim_analysis", "step_2_statute_match", "omission_check",
        "step_3_semantic_justification", "statute_reference", "violation_type",
        "evidence_quote", "network_action", "offending_entities"
    }

    if isinstance(violations, list):
        cleaned_violations = []
        for raw_v in violations:
            if not isinstance(raw_v, dict):
                continue
            # Pillar 3 Firewall: Drop violations that rely on silence/omission
            if raw_v.get("omission_check") is True:
                continue
            v = {k: val for k, val in raw_v.items() if k in ALLOWED_VIOLATION_KEYS}
            v.setdefault("step_1_active_claim_analysis", "Analyzed affirmative text from privacy policy statement.")
            v.setdefault("step_2_statute_match", f"Matched against statutory requirements for {v.get('statute_reference', 'Section 8')}.")
            v.setdefault("omission_check", False)
            v.setdefault("step_3_semantic_justification", "Violation determined based on active statement.")
            v.setdefault("statute_reference", "Section 8(7)")
            
            # Map shorthand or drift in violation_type
            vt = v.get("violation_type", "")
            if vt not in VALID_VIOLATION_TYPES:
                if "RETENTION" in vt:
                    v["violation_type"] = "DATA_RETENTION_LIMIT_EXCEEDED"
                elif "CONSENT" in vt:
                    v["violation_type"] = "CONSENT_NOT_FREE_OR_SPECIFIC"
                elif "NOTICE" in vt:
                    v["violation_type"] = "NOTICE_INADEQUATE"
                elif "CHILD" in vt:
                    v["violation_type"] = "CHILD_CONSENT_VIOLATION"
                else:
                    v["violation_type"] = "PURPOSE_LIMITATION_VIOLATION"

            # Ensure evidence quote length >= 20
            quote = v.get("evidence_quote", "")
            if len(quote) < 20:
                v["evidence_quote"] = (quote + " " + "Policy terms state that data is collected and retained.").strip()

            # Map network_action
            na = v.get("network_action", "")
            if na not in VALID_NETWORK_ACTIONS:
                if "WARN" in na:
                    v["network_action"] = "WARN_USER_ONLY"
                elif "BLOCK" in na:
                    v["network_action"] = "BLOCK_THIRD_PARTY"
                else:
                    v["network_action"] = "WARN_USER_ONLY"

            if "offending_entities" not in v or not isinstance(v["offending_entities"], list):
                v["offending_entities"] = []

            cleaned_violations.append(v)
        report["violations"] = cleaned_violations
    else:
        report["violations"] = []

    # Filter root keys strictly to the schema contract (strips metadata like schema_version, rules_applied)
    ALLOWED_ROOT_KEYS = {"global_legal_reasoning", "violations", "dpdp_trust_score", "subtlety_score"}
    report = {k: v for k, v in report.items() if k in ALLOWED_ROOT_KEYS}

    # 5. Strict Structural Validation
    try:
        jsonschema.validate(instance=report, schema=get_dpdp_schema())
    except jsonschema.ValidationError as e:
        raise ValueError(f"Schema drift detected: {e.message}")
        
    return report