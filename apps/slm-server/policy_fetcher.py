#!/usr/bin/env python3
"""
policy_fetcher.py — Server-Side Privacy Policy Extractor

Replaces the browser-side fetch+parse pipeline that previously ran in the
extension's content-script and service-worker PROXY_FETCH handler.

Moving extraction server-side means:
  - The extension sends a tiny URL string instead of ~20 KB of policy text.
  - The server can use proper async HTTP with retry, browser-like headers,
    redirect following, and encoding detection — all much more reliable than
    the extension's fetch() which is subject to CORS, service-worker memory
    limits, and CSP of the embedding page.
  - The raw policy text is used once for inference, then discarded. It is
    never stored in the audit_store or returned to the extension.

Algorithm (mirrors extractor-core.ts exactly, now authoritative):
  1. Async HTTP fetch via httpx (browser headers, redirect follow, 20s timeout)
  2. Encoding detection via chardet fallback
  3. BeautifulSoup4 noise removal (script/style/nav/header/footer/banners)
  4. Content selection: CSS selector priority list → Readability link-density
  5. Language filter: drop lines ≥30% non-Latin-script characters
  6. Normalise whitespace, truncate to MAX_POLICY_CHARS
  7. Return FetchResult (text + SHA-256 hash + telemetry). Raw text is the
     caller's responsibility to discard after inference.
"""

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import httpx
try:
    import h2  # noqa: F401
    _HAS_HTTP2 = True
except ImportError:
    _HAS_HTTP2 = False
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_POLICY_CHARS   = 32_000
MIN_POLICY_CHARS   = 500
FETCH_TIMEOUT_S    = 20
MAX_RESPONSE_BYTES = 8 * 1024 * 1024   # 8 MB hard cap
MAX_REDIRECTS      = 6

# Noise tags removed before content selection
_NOISE_TAGS = {
    "script", "style", "nav", "header", "aside", "footer",
    "form", "noscript", "iframe", "svg", "canvas",
}

# CSS class/id fragments that reliably indicate non-policy chrome widgets.
# Using delimiter boundaries so we don't accidentally match Tailwind
# classes (e.g. pt-[calc(var(--banner-min-height))]) or legal clause titles
# (e.g. <section id="consent">, <div id="gdpr-rights">, #CookiebotDeclaration).
_NOISE_PATTERNS = re.compile(
    r"(?:^|[-_ \t])(?:"
    r"cookie[-_]?(?:banner|notice|popup|bar|modal|alert|dialog|wrap)|"
    r"consent[-_]?(?:banner|modal|popup|bar|dialog)|"
    r"gdpr[-_]?(?:banner|notice|modal|popup)|"
    r"banner[-_]?(?:wrapper|top|header|promo|overlay)|"
    r"modal[-_]?(?:overlay|backdrop|wrapper)|"
    r"popup[-_]?(?:overlay|wrapper|container)|"
    r"newsletter|social[-_]?(?:share|links|icons)|"
    r"ad[-_]?(?:slot|banner|container|wrapper|unit)|"
    r"sidebar[-_]?(?:nav|menu|wrapper)|toolbar"
    r")(?:$|[-_ \t])",
    re.I,
)

# Client-side meta-refresh redirect patterns
_META_REFRESH_RE = re.compile(
    r'<meta[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\']?[^"\'>]*url=([^"\'>\s]+)',
    re.I,
)
_META_REFRESH_RE_ALT = re.compile(
    r'<meta[^>]*content=["\']?[^"\'>]*url=([^"\'>\s]+)["\']?[^>]*http-equiv=["\']?refresh',
    re.I,
)

# Fixed CSS selectors tried in priority order (mirrors CONTENT_SELECTORS in
# extractor-core.ts; keep in sync if the TS version changes)
_CONTENT_SELECTORS = [
    "main", "article", '[role="main"]',
    ".policy-content", ".privacy-content", ".policy-body", ".legal-content",
    ".entry-content", ".rte", ".markdown-body", ".prose",
    '[itemprop="text"]',
    "#privacy", "#policy", ".content", "#content",
    # Modern privacy-page patterns used by popular CMS / compliance platforms
    ".privacy-policy", ".terms-content", ".legal-text", ".page-content",
    ".page-body", ".single-content", ".post-content",
    '[data-testid="privacy-policy"]', '[data-testid="policy-content"]',
    '#privacy-policy', '#terms', '#legal',
    # Compliance platform wrappers (OneTrust, TrustArc, Cookiebot, etc.)
    '#ot-sdk-txt', '.otnotice-content', '.truste-content',
    '.uc-embed', '#CookiebotDeclaration',
]

# Non-Latin Unicode ranges (Devanagari → CJK; matches extractor-core.ts)
_NON_LATIN_RE = re.compile(
    r"[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF"
    r"\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF"
    r"\u0D00-\u0D7F\u0D80-\u0DFF\u0600-\u06FF\u0750-\u077F"
    r"\u0E00-\u0E7F\u0590-\u05FF\u4E00-\u9FFF\u3040-\u30FF"
    r"\u31F0-\u31FF\uAC00-\uD7AF]"
)
_NON_LATIN_LINE_THRESHOLD = 0.30   # drop line if ≥30% non-Latin chars

# Browser-like request headers — full Chromium 136 Client Hints set.
# Modern WAFs (Cloudflare, Akamai, Imperva, AWS WAF) fingerprint requests
# missing Sec-CH-UA / Sec-Fetch-* headers and return 403/503.  These headers
# replicate exactly what Chrome 136 sends for a top-level document navigation.
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    # ── Chromium Client Hints (WAF bypass) ──────────────────────────────
    "Sec-CH-UA": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    # ── Sec-Fetch metadata (proves top-level navigation intent) ────────
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    # Upgrade-Insecure-Requests signals browser-like TLS upgrade behaviour
    "Upgrade-Insecure-Requests": "1",
    # Priority hints (Chrome sends these for the main document request)
    "Priority": "u=0, i",
}

# ─── In-memory fetch cache (5-min TTL, bounded LRU) ───────────────────────────
# Prevents duplicate network requests when several users trigger audits for the
# same domain within the same short window.
# BUG FIX: this used to be a plain dict with no size cap and no eviction of
# expired entries — every distinct policyUrl ever fetched stayed resident in
# process memory forever (a slow, unbounded leak at "10k+ users, many
# different sites" scale). Now a bounded LRU: capped at _FETCH_CACHE_MAXSIZE
# entries, oldest evicted first once full.
_FETCH_CACHE_MAXSIZE = 2048
_FETCH_CACHE_TTL = 300   # seconds
_fetch_cache: "OrderedDict[str, Tuple[float, FetchResult]]" = OrderedDict()


def _fetch_cache_get(url: str) -> Optional["FetchResult"]:
    entry = _fetch_cache.get(url)
    if entry is None:
        return None
    cached_at, result = entry
    if time.monotonic() - cached_at >= _FETCH_CACHE_TTL:
        _fetch_cache.pop(url, None)
        return None
    _fetch_cache.move_to_end(url)
    return result


def _fetch_cache_put(url: str, result: "FetchResult") -> None:
    _fetch_cache[url] = (time.monotonic(), result)
    _fetch_cache.move_to_end(url)
    while len(_fetch_cache) > _FETCH_CACHE_MAXSIZE:
        _fetch_cache.popitem(last=False)


# ─── Result type ──────────────────────────────────────────────────────────────
@dataclass
class FetchResult:
    text: str             # clean, English-only, truncated policy text
    policy_hash: str      # SHA-256 of text (for change detection in audit_store)
    policy_url: str       # final URL after redirects
    fetch_ms: int
    char_count: int
    stripped_line_count: int
    truncated: bool
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.text) >= MIN_POLICY_CHARS


# ─── Core helpers ─────────────────────────────────────────────────────────────
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_noise_element(tag: Tag) -> bool:
    if not hasattr(tag, "name") or not tag.name or getattr(tag, "decomposed", False):
        return False
    # Never treat the main content root or structural article as noise
    if tag.name in ("main", "article", "body", "html"):
        return False
    if tag.get("role") == "main":
        return False
    # Never treat explicitly targeted content IDs as noise
    tag_id = str(tag.get("id", ""))
    if tag_id and any(sel.strip("#") == tag_id for sel in _CONTENT_SELECTORS if sel.startswith("#")):
        return False
    if tag.name in _NOISE_TAGS:
        return True
    # Substantive content guard: never decompose a container holding > 800 chars of text
    if len(tag.get_text()) > 800:
        return False
    attrs = getattr(tag, "attrs", None)
    if not isinstance(attrs, dict):
        return False
    classes_val = attrs.get("class", [])
    classes = " ".join(classes_val) if isinstance(classes_val, list) else str(classes_val)
    return bool(_NOISE_PATTERNS.search(classes) or _NOISE_PATTERNS.search(tag_id))


def _link_density(tag: Tag) -> float:
    text_len = len(tag.get_text())
    if text_len == 0:
        return 1.0
    link_len = sum(len(a.get_text()) for a in tag.find_all("a"))
    return min(1.0, link_len / text_len)


def _select_content(soup: BeautifulSoup) -> str:
    """
    Priority 1: Fixed CSS selectors (fastest, covers ~80% of real policy pages)
    Priority 2: Readability-style link-density scoring (covers the rest)
    Fallback: entire <body>

    Uses '\n' separator to preserve paragraph & list structure for both
    multilingual line filtering and downstream paragraph-aware chunking.
    """
    for sel in _CONTENT_SELECTORS:
        try:
            el = soup.select_one(sel)
        except Exception:
            continue
        if el:
            text = el.get_text("\n", strip=True)
            if len(text) >= MIN_POLICY_CHARS:
                return text

    # Readability fallback — score every block element, prefer dense prose
    best_score = 0.0
    best_text  = ""
    for tag in soup.find_all(["div", "section", "article", "main"])[:400]:
        text = tag.get_text("\n", strip=True)
        text_len = len(text)
        if text_len < MIN_POLICY_CHARS:
            continue
        score = text_len * (1.0 - _link_density(tag))
        if score > best_score:
            best_score = score
            best_text  = text

    return best_text or (soup.body.get_text("\n", strip=True) if soup.body else "")


# ─── CSR / SPA Hydration Fallback ─────────────────────────────────────────────
# Many modern sites (Next.js, Nuxt, React, Remix) serve a bare shell with all
# content in a hydration JSON blob or RSC stream chunks. When _select_content()
# returns < MIN_POLICY_CHARS, this fallback extracts prose from the raw HTML
# before giving up.

def _walk_json_strings(obj: Any, min_len: int = 50) -> List[str]:
    """Recursively collect string values that look like prose paragraphs."""
    results: list[str] = []
    if isinstance(obj, str):
        # Only keep strings that are long enough and contain spaces (prose)
        stripped = obj.strip()
        if len(stripped) >= min_len and " " in stripped:
            results.append(stripped)
    elif isinstance(obj, dict):
        for v in obj.values():
            results.extend(_walk_json_strings(v, min_len))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            results.extend(_walk_json_strings(item, min_len))
    return results


def _extract_hydration_text(html: str) -> str:
    """
    Fallback extraction for CSR/SPA pages where the visible DOM is a bare
    shell but the real content lives in a JSON hydration blob or RSC stream.

    Operates directly on the raw HTML string to ensure <script> tags
    decomposed from the visual DOM tree are fully accessible.

    Attempts, in priority order:
      1. Next.js Pages — <script id="__NEXT_DATA__"> JSON blob → walk props tree
      2. Next.js 13+ App Router — RSC streaming chunks: self.__next_f.push(...)
      3. Nuxt.js — Nuxt 3 <script id="__NUXT_DATA__"> or Nuxt 2 window.__NUXT__
      4. Remix — window.__remixContext
      5. JSON-LD — <script type="application/ld+json"> → articleBody / text

    Returns the concatenated prose strings, or "" if nothing useful is found.
    """
    collected: list[str] = []

    # ── 1. Next.js Pages __NEXT_DATA__ ─────────────────────────────────────
    next_match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if next_match:
        try:
            data = json.loads(next_match.group(1))
            # The page content typically lives under props.pageProps
            page_props = data.get("props", {}).get("pageProps", data)
            collected.extend(_walk_json_strings(page_props))
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 2. Next.js 13+ App Router (React Server Component streaming) ───────
    if not collected:
        rsc_matches = re.findall(r'self\.__next_f\.push\(\[\d+,\s*"(.*?)"\]\)', html, re.S)
        for chunk in rsc_matches:
            try:
                decoded = json.loads(f'"{chunk}"')
                chunk_soup = BeautifulSoup(decoded, "html.parser")
                chunk_text = chunk_soup.get_text("\n", strip=True)
                for line in chunk_text.splitlines():
                    s = line.strip()
                    if len(s) >= 50 and " " in s:
                        collected.append(s)
            except Exception:
                pass

    # ── 3. Nuxt.js (Nuxt 3 __NUXT_DATA__ or Nuxt 2 window.__NUXT__) ────────
    if not collected:
        nuxt3_match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if nuxt3_match:
            try:
                data = json.loads(nuxt3_match.group(1))
                collected.extend(_walk_json_strings(data))
            except (json.JSONDecodeError, TypeError):
                pass
    if not collected:
        nuxt2_match = re.search(r'window\.__NUXT__\s*=\s*([{\[].+?[}\]]);?\s*</script>', html, re.S)
        if nuxt2_match:
            try:
                data = json.loads(nuxt2_match.group(1))
                collected.extend(_walk_json_strings(data))
            except (json.JSONDecodeError, TypeError):
                pass

    # ── 4. Remix / React Router (window.__remixContext) ───────────────────
    if not collected:
        remix_match = re.search(r'window\.__remixContext\s*=\s*({.+?});?\s*</script>', html, re.S)
        if remix_match:
            try:
                data = json.loads(remix_match.group(1))
                collected.extend(_walk_json_strings(data))
            except (json.JSONDecodeError, TypeError):
                pass

    # ── 5. JSON-LD structured data ─────────────────────────────────────────
    if not collected:
        ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
        for ld_str in ld_matches:
            try:
                ld = json.loads(ld_str)
                # articleBody is the canonical field for page text
                for key in ("articleBody", "text", "description"):
                    val = ld.get(key) if isinstance(ld, dict) else None
                    if isinstance(val, str) and len(val) >= MIN_POLICY_CHARS:
                        collected.append(val)
            except (json.JSONDecodeError, TypeError):
                pass

    if not collected:
        return ""

    text = "\n\n".join(collected)
    print(
        f"🔄 [PolicyFetcher] Hydration fallback recovered {len(text)} chars "
        f"from CSR/SPA state blob."
    )
    return text


def _strip_non_english(text: str) -> Tuple[str, int]:
    """Drop lines whose non-Latin character ratio ≥ threshold."""
    lines = text.splitlines()
    dropped = 0
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        non_latin = len(_NON_LATIN_RE.findall(stripped))
        if non_latin / len(stripped) >= _NON_LATIN_LINE_THRESHOLD:
            dropped += 1
        else:
            kept.append(line)
    return "\n".join(kept), dropped


def _clean_text(raw: str) -> str:
    """Collapse runs of whitespace and format into clean, readable paragraphs."""
    lines = [l.strip() for l in raw.splitlines()]
    paragraphs: list[str] = []
    current_p: list[str] = []
    for line in lines:
        if line:
            current_p.append(line)
        elif current_p:
            paragraphs.append(" ".join(current_p))
            current_p = []
    if current_p:
        paragraphs.append(" ".join(current_p))
    return "\n\n".join(paragraphs)


# ─── SSRF guard ────────────────────────────────────────────────────────────────
# This server fetches an attacker-influenceable URL (the extension sends
# {domain, policyUrl} straight from the audited page) directly from inside the
# deployment's network — which can also reach internal-only peers (Redis on
# the Docker bridge network, cloud metadata endpoints like 169.254.169.254,
# etc). Without this guard, `/v1/audit/by-url` would be a textbook SSRF: any
# caller holding a valid API key (or a leaked/replayed one) could make the
# server probe or fetch from arbitrary internal addresses and get the
# extracted "policy text" of the response back in the audit report.
def _is_blocked_ip(ip) -> bool:
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def _resolve_and_check_host(hostname: str) -> Optional[str]:
    """Returns an error string if `hostname` fails to resolve, or resolves to
    ANY private/internal/reserved address, else None (safe to fetch)."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return f"Could not resolve host '{hostname}'."
    if not infos:
        return f"Could not resolve host '{hostname}'."
    for info in infos:
        raw_ip = info[4][0].split("%")[0]   # strip IPv6 zone id, if present
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            return f"'{hostname}' resolves to a private/internal address ({raw_ip}) — refused."
    return None


def _validate_fetch_url(url: str) -> Optional[str]:
    """SSRF guard, applied to the initial URL AND every redirect hop (a
    malicious/compromised site could 30x a public initial URL to an internal
    address). Returns an error string if the URL must NOT be fetched, else
    None.

    KNOWN RESIDUAL GAP (documented, not yet fixed): this resolves and checks
    the hostname HERE, but the actual connection in _fetch_with_redirects()
    below performs its OWN separate DNS resolution via httpx/httpcore. A
    malicious DNS server with a very short TTL could return a safe IP for
    THIS check and a different, internal IP by the time the real connection
    resolves — a narrow, sophisticated DNS-rebinding window. Closing this
    fully requires pinning the connection to the exact IP validated here
    (bypassing httpx's own resolution), which touches TLS/SNI handling and
    needs a real test environment to verify correctness — not attempted
    without one. Left as an explicit, tracked gap rather than an unverified
    "fix" that might silently break TLS to legitimate sites.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return "Only http:// and https:// policy URLs are supported."
    hostname = parts.hostname
    if not hostname:
        return "Policy URL has no host."
    return _resolve_and_check_host(hostname)


class _FetchRefused(Exception):
    """Raised when the SSRF guard rejects the initial URL or a redirect hop."""
    def __init__(self, url: str, reason: str):
        self.url    = url
        self.reason = f"Refused: {reason}"
        super().__init__(self.reason)


class _TlsVerificationFailed(Exception):
    """Raised when the verified (verify=True) request fails specifically due
    to a TLS/certificate problem, so the caller can decide whether to retry
    unverified — as opposed to a DNS/connection-refused/timeout failure,
    which should just fail outright rather than silently disabling TLS
    verification."""


def _is_tls_error(exc: BaseException) -> bool:
    import ssl
    cause = exc
    seen = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(cause, ssl.SSLError):
            return True
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
    return False


async def _fetch_with_redirects(url: str, verify: bool) -> Tuple[httpx.Response, bytes, str]:
    """Issue the request, following redirects manually (up to MAX_REDIRECTS)
    so the SSRF guard can be re-applied to every hop's target — not just the
    initial URL. Streams the body with a hard MAX_RESPONSE_BYTES cap enforced
    DURING download (rather than trimming an already-fully-buffered string
    afterward, which does nothing to bound memory use for a huge or
    slow-drip response).

    Returns (response, body_bytes, final_url). Raises _FetchRefused if the
    guard rejects any hop, _TlsVerificationFailed if `verify=True` and the
    handshake fails on a certificate problem specifically, or lets
    httpx.TimeoutException / other exceptions propagate as-is.
    """
    current_url = url
    # Inject a Referer header matching the target site — many WAFs reject
    # requests with no Referer since real browsers always send one.
    parts = urlsplit(url)
    fetch_headers = {
        **_REQUEST_HEADERS,
        "Referer": f"{parts.scheme}://{parts.netloc}/",
    }
    async with httpx.AsyncClient(
        headers=fetch_headers,
        timeout=httpx.Timeout(FETCH_TIMEOUT_S),
        verify=verify,
        http2=False,  # HTTP/1.1 avoids JA4 HTTP/2 frame fingerprinting on Cloudflare WAFs
    ) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            try:
                request = client.build_request("GET", current_url)
                resp = await client.send(request, follow_redirects=False, stream=True)
            except httpx.ConnectError as exc:
                if verify and _is_tls_error(exc):
                    raise _TlsVerificationFailed() from exc
                raise

            if resp.is_redirect:
                next_url = resp.headers.get("location")
                await resp.aclose()
                if not next_url:
                    raise RuntimeError(f"Redirect from {current_url} had no Location header.")
                # Resolve relative redirects against the current URL.
                next_url = str(httpx.URL(current_url).join(next_url))
                hop_err = _validate_fetch_url(next_url)
                if hop_err:
                    raise _FetchRefused(next_url, f"redirect target — {hop_err}")
                current_url = next_url
                continue

            # Stream the body ourselves so we can abort as soon as the size
            # cap is exceeded, instead of only checking it once everything
            # has already been buffered into memory.
            body = bytearray()
            async for chunk in resp.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    await resp.aclose()
                    raise RuntimeError(f"Response exceeded {MAX_RESPONSE_BYTES}-byte cap; aborted mid-download.")
            await resp.aclose()
            return resp, bytes(body), str(resp.url)

    raise RuntimeError(f"Too many redirects (> {MAX_REDIRECTS}) starting from {url}.")


# ─── Main async fetch entry point ─────────────────────────────────────────────
async def fetch_policy(url: str, force: bool = False) -> FetchResult:
    """
    Fetch and extract the policy at `url`.
    Results are cached for FETCH_CACHE_TTL seconds to absorb bursts.
    Pass force=True to bypass the cache.
    """
    if not force:
        cached = _fetch_cache_get(url)
        if cached is not None:
            return cached

    result = await _do_fetch(url)

    # Only cache successful fetches; let errors be re-tried immediately
    if result.ok:
        _fetch_cache_put(url, result)
    return result


async def _do_fetch(url: str, _hops: int = 0) -> FetchResult:
    t0 = time.monotonic()

    guard_err = _validate_fetch_url(url)
    if guard_err:
        return FetchResult(
            text="", policy_hash="", policy_url=url,
            fetch_ms=int((time.monotonic() - t0) * 1000),
            char_count=0, stripped_line_count=0, truncated=False,
            error=f"Refused: {guard_err}",
        )

    final_url = url
    try:
        resp, body, final_url = await _fetch_with_redirects(url, verify=True)
    except _TlsVerificationFailed:
        # BUG FIX: verify=False used to be applied unconditionally to every
        # fetch (blanket MITM exposure) just to accommodate the occasional
        # policy page with an expired/self-signed cert. Now: verify normally,
        # and only fall back to an unverified retry on an actual TLS failure.
        print(f"⚠️  [PolicyFetcher] TLS verification failed for {url[:80]}… retrying unverified.")
        try:
            resp, body, final_url = await _fetch_with_redirects(url, verify=False)
        except _FetchRefused as exc:
            return FetchResult(
                text="", policy_hash="", policy_url=exc.url, fetch_ms=int((time.monotonic() - t0) * 1000),
                char_count=0, stripped_line_count=0, truncated=False, error=exc.reason,
            )
        except httpx.TimeoutException:
            return FetchResult(
                text="", policy_hash="", policy_url=final_url,
                fetch_ms=int((time.monotonic() - t0) * 1000),
                char_count=0, stripped_line_count=0, truncated=False,
                error=f"Fetch timed out after {FETCH_TIMEOUT_S}s.",
            )
        except Exception as exc:
            return FetchResult(
                text="", policy_hash="", policy_url=final_url,
                fetch_ms=int((time.monotonic() - t0) * 1000),
                char_count=0, stripped_line_count=0, truncated=False, error=str(exc),
            )
    except _FetchRefused as exc:
        return FetchResult(
            text="", policy_hash="", policy_url=exc.url, fetch_ms=int((time.monotonic() - t0) * 1000),
            char_count=0, stripped_line_count=0, truncated=False, error=exc.reason,
        )
    except httpx.TimeoutException:
        return FetchResult(
            text="", policy_hash="", policy_url=final_url,
            fetch_ms=int((time.monotonic() - t0) * 1000),
            char_count=0, stripped_line_count=0, truncated=False,
            error=f"Fetch timed out after {FETCH_TIMEOUT_S}s.",
        )
    except Exception as exc:
        return FetchResult(
            text="", policy_hash="", policy_url=final_url,
            fetch_ms=int((time.monotonic() - t0) * 1000),
            char_count=0, stripped_line_count=0, truncated=False,
            error=str(exc),
        )

    fetch_ms = int((time.monotonic() - t0) * 1000)

    content_type = resp.headers.get("content-type", "")
    if "pdf" in content_type or bytes(body[:5]) == b"%PDF-":
        return FetchResult(
            text="", policy_hash="", policy_url=final_url,
            fetch_ms=fetch_ms, char_count=0, stripped_line_count=0,
            truncated=False,
            error="PDF policies are not yet supported by the server extractor.",
        )

    if resp.status_code >= 400:
        return FetchResult(
            text="", policy_hash="", policy_url=final_url,
            fetch_ms=fetch_ms, char_count=0, stripped_line_count=0,
            truncated=False, error=f"HTTP {resp.status_code}",
        )

    # ── Robust encoding detection ──────────────────────────────────────────
    encoding = resp.charset_encoding or resp.encoding
    if not encoding or encoding.lower() in ("ascii", "us-ascii"):
        encoding = "utf-8"
    try:
        html = body.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        try:
            from bs4 import UnicodeDammit
            dammit = UnicodeDammit(body)
            html = dammit.unicode_markup or body.decode("utf-8", errors="replace")
        except Exception:
            html = body.decode("utf-8", errors="replace")

    # ── Client-side meta refresh follower ──────────────────────────────────
    # Google (google.com/policies/privacy/) and enterprise portals return 200
    # with an HTML redirect shell: <meta http-equiv="refresh" content="0; URL=...">
    if _hops < MAX_REDIRECTS:
        refresh_match = _META_REFRESH_RE.search(html) or _META_REFRESH_RE_ALT.search(html)
        if refresh_match:
            target_path = refresh_match.group(1).strip("'\"")
            target_url = str(httpx.URL(final_url).join(target_path))
            if target_url != final_url:
                guard_err = _validate_fetch_url(target_url)
                if not guard_err:
                    print(f"🔄 [PolicyFetcher] Following client-side meta refresh: {final_url} → {target_url}")
                    return await _do_fetch(target_url, _hops=_hops + 1)

    # ── Parse ──────────────────────────────────────────────────────────────
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Remove comments and noise elements in one pass
    for node in soup.find_all(string=lambda t: isinstance(t, Comment)):
        node.extract()
    for tag in soup.find_all(True):
        if _is_noise_element(tag):
            tag.decompose()

    # ── Content selection ──────────────────────────────────────────────────
    raw_text = _select_content(soup)

    # ── CSR/SPA hydration fallback ─────────────────────────────────────────
    # If the visible DOM produced < MIN_POLICY_CHARS, the page is likely
    # a Next.js / Nuxt / React SPA whose real content lives in a JSON
    # hydration blob or RSC stream embedded in raw HTML scripts.
    if len(raw_text) < MIN_POLICY_CHARS:
        hydration = _extract_hydration_text(html)
        if len(hydration) > len(raw_text):
            raw_text = hydration

    # ── Language filter ────────────────────────────────────────────────────
    english_text, stripped = _strip_non_english(raw_text)
    clean = _clean_text(english_text)

    if len(clean) < MIN_POLICY_CHARS:
        return FetchResult(
            text="", policy_hash="", policy_url=final_url,
            fetch_ms=int((time.monotonic() - t0) * 1000),
            char_count=len(clean), stripped_line_count=stripped, truncated=False,
            error=(
                f"Extracted text too short ({len(clean)} chars) — "
                "page may be JS-rendered or blocked."
            ),
        )

    # ── Truncation ─────────────────────────────────────────────────────────
    truncated = len(clean) > MAX_POLICY_CHARS
    if truncated:
        clean = clean[:MAX_POLICY_CHARS]

    policy_hash = _sha256(clean)
    total_ms    = int((time.monotonic() - t0) * 1000)

    print(
        f"🔍 [PolicyFetcher] {final_url[:60]}… "
        f"→ {len(clean)} chars, {stripped} lines stripped, "
        f"{'truncated, ' if truncated else ''}{total_ms}ms"
    )

    return FetchResult(
        text=clean,
        policy_hash=policy_hash,
        policy_url=final_url,
        fetch_ms=total_ms,
        char_count=len(clean),
        stripped_line_count=stripped,
        truncated=truncated,
    )
