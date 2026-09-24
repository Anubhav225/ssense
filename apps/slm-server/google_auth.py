#!/usr/bin/env python3
"""
google_auth.py — Server-side verification of Google identity tokens.

Why this exists
---------------
The original /v1/auth/register endpoint trusted whatever e-mail the client sent.
Because registering an existing e-mail returns that user's existing API key and
HMAC secret, anyone who typed a victim's address could take over their account
(and their synced history).  Sign-in is now proven with a Google token that the
extension obtains via chrome.identity; this module validates it against Google
before any credentials are issued.

Accepted inputs
---------------
  * OAuth2 access token  (chrome.identity.getAuthToken / launchWebAuthFlow)
  * OpenID Connect ID token (JWT)

Both are verified through Google's tokeninfo endpoint, and the token's audience
must match one of SSENSE_GOOGLE_CLIENT_IDS (comma-separated) so a token minted
for some *other* app cannot be replayed here.
"""

import os
from dataclasses import dataclass
from typing import List, Optional

import httpx

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleAuthError(Exception):
    """Raised with an HTTP-friendly status + safe message."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class GoogleIdentity:
    email: str
    sub: str
    name: str
    picture: Optional[str]


def allowed_client_ids() -> List[str]:
    raw = os.getenv("SSENSE_GOOGLE_CLIENT_IDS", "")
    return [c.strip() for c in raw.split(",") if c.strip()]


def google_auth_configured() -> bool:
    return bool(allowed_client_ids()) or _skip_aud_check()


def _skip_aud_check() -> bool:
    # Development escape hatch only. Never enable in production: without an
    # audience check, a token issued to any third-party app would be accepted.
    return os.getenv("SSENSE_GOOGLE_SKIP_AUD_CHECK", "").strip().lower() in ("1", "true", "yes")


def require_google_auth() -> bool:
    """True (default) = anonymous / e-mail-only registration is refused."""
    return os.getenv("SSENSE_REQUIRE_GOOGLE_AUTH", "true").strip().lower() in ("1", "true", "yes")


async def verify_google_token(
    token: str,
    token_type: str = "access_token",
    client: Optional[httpx.AsyncClient] = None,
) -> GoogleIdentity:
    token = (token or "").strip()
    if len(token) < 20 or len(token) > 4096:
        raise GoogleAuthError("Malformed Google token.", 400)
    if token_type not in ("access_token", "id_token"):
        raise GoogleAuthError("Unsupported token type.", 400)
    if not google_auth_configured():
        raise GoogleAuthError(
            "Google sign-in is not configured on this server (set SSENSE_GOOGLE_CLIENT_IDS).", 503
        )

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=8.0)
    try:
        try:
            r = await client.get(TOKENINFO_URL, params={token_type: token})
        except httpx.HTTPError:
            raise GoogleAuthError("Could not reach Google to verify sign-in. Try again.", 503)
        if r.status_code != 200:
            raise GoogleAuthError("Google rejected this sign-in token.", 401)
        info = r.json()

        aud = info.get("aud") or info.get("azp") or ""
        allowed = allowed_client_ids()
        if allowed:
            if aud not in allowed and info.get("azp") not in allowed:
                raise GoogleAuthError("Token was not issued for this application.", 401)
        elif not _skip_aud_check():
            raise GoogleAuthError("Google sign-in is not configured on this server.", 503)

        email = (info.get("email") or "").strip().lower()
        verified = str(info.get("email_verified", "")).lower() == "true"
        if not email or not verified:
            raise GoogleAuthError("Your Google account e-mail is missing or unverified.", 401)

        name = (info.get("name") or "").strip()
        picture = info.get("picture")

        # Access tokens don't carry profile fields in tokeninfo; fetch them.
        if token_type == "access_token" and (not name or not picture):
            try:
                u = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {token}"})
                if u.status_code == 200:
                    ui = u.json()
                    name = name or (ui.get("name") or "").strip()
                    picture = picture or ui.get("picture")
            except httpx.HTTPError:
                pass  # profile fields are cosmetic

        return GoogleIdentity(
            email=email,
            sub=str(info.get("sub") or ""),
            name=name or email.split("@")[0].replace(".", " ").title(),
            picture=picture,
        )
    finally:
        if owns_client:
            await client.aclose()
