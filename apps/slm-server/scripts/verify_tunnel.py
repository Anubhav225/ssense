#!/usr/bin/env python3
"""
verify_tunnel.py — Automated Cloudflare Public Tunnel & Custom Domain Verifier

Verifies:
  1. Ephemeral Random Quick Tunnel (trycloudflare.com)
  2. Permanent Named Custom Domain (e.g. https://api.yourdomain.com)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def find_cloudflared() -> str:
    bin_name = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"
    existing = shutil.which(bin_name) or shutil.which("cloudflared")
    if existing:
        return existing
    if sys.platform == "win32":
        candidates = [
            Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
            Path(r"C:\Program Files\cloudflared\cloudflared.exe"),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "cloudflared" / "cloudflared.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "cloudflared" / "cloudflared.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "cloudflared.exe",
            Path(r"C:\ProgramData\chocolatey\bin\cloudflared.exe"),
        ]
        for c in candidates:
            if c.is_file():
                return str(c)
    return ""


def test_endpoint(url: str, timeout: int = 15) -> bool:
    target = url.rstrip("/") + "/health"
    print(f"🌐 Verifying HTTPS connection to {target} via public internet...")
    req = urllib.request.Request(target, headers={"User-Agent": "Ssense-Verifier/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ SUCCESS! Public endpoint is reachable and responding:")
            print(f"   Status: {data.get('status')}")
            print(f"   Compute Profile: {data.get('compute_profile')}")
            print(f"   Engine Ready: {data.get('engine_ready')}")
            print(f"   Backend: {data.get('backend')}")
            return True
    except Exception as e:
        print(f"❌ Verification failed for {target}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Verify Cloudflare Tunnel connectivity")
    parser.add_argument("--domain", type=str, default=os.getenv("CLOUDFLARE_DOMAIN", ""), help="Bought domain to verify (e.g. https://api.yourdomain.com)")
    parser.add_argument("--port", type=int, default=8000, help="Local server port (default: 8000)")
    args = parser.parse_args()

    print("═══════════════════════════════════════════════════════════════════")
    print("🔍 Ssense Cloudflare Public Connection Verifier")
    print("═══════════════════════════════════════════════════════════════════")

    # If user provided or bought a custom domain, verify it directly
    if args.domain:
        domain = args.domain.strip()
        if not domain.startswith("http://") and not domain.startswith("https://"):
            domain = "https://" + domain
        print(f"🎯 Testing specified custom domain: {domain}")
        success = test_endpoint(domain)
        sys.exit(0 if success else 1)

    # Otherwise verify quick tunnel random domain generation
    cloudflared = find_cloudflared()
    if not cloudflared:
        print("❌ Could not locate cloudflared binary.")
        sys.exit(1)

    print(f"⚡ Testing random domain generation on port {args.port}...")
    cmd = [cloudflared, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{args.port}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

    url = None
    pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    start = time.time()
    while time.time() - start < 25:
        line = proc.stdout.readline()
        if not line:
            break
        m = pattern.search(line)
        if m:
            url = m.group(0)
            break

    if not url:
        print("❌ Could not generate random trycloudflare.com tunnel URL.")
        proc.terminate()
        sys.exit(1)

    print(f"🎉 Random tunnel domain generated: {url}")
    time.sleep(3)
    success = test_endpoint(url)
    proc.terminate()
    proc.wait(timeout=5)
    print("🛑 Verification completed cleanly.")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
