#!/usr/bin/env python3
"""
start_lab_tunnel.py — Professional Zero-Config Tunnel & Global Domain Synchronizer

Enables your Ssense SLM Server running on an AGX Spark (or any lab machine)
to be accessed securely over HTTPS from ANY laptop in the world without:
  1. Purchasing a domain name
  2. Setting up static IPs or router port forwarding
  3. Manually typing IP addresses into extensions

Usage:
    python scripts/start_lab_tunnel.py [--port 8000] [--token YOUR_CLOUDFLARE_TOKEN]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def update_env_file(file_path: Path, key: str, value: str) -> bool:
    """Safely updates or adds a KEY=VALUE line in an env file."""
    if not file_path.exists():
        file_path.write_text(f"{key}={value}\n", encoding="utf-8")
        return True

    lines = file_path.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    found = False
    new_lines = []

    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")

    file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def find_or_download_cloudflared() -> str:
    """Finds cloudflared in PATH, standard installation directories, or local directory."""
    bin_name = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"
    existing = shutil.which(bin_name) or shutil.which("cloudflared")
    if existing:
        return existing

    # Standard Windows install locations (winget, MSI, chocolatey)
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

    local_bin = Path(__file__).resolve().parent / bin_name
    if local_bin.exists():
        return str(local_bin)

    print("⚡ 'cloudflared' not found in PATH.")
    print("   To install cloudflared:")
    if sys.platform == "win32":
        print("   winget install --id Cloudflare.cloudflared   OR   choco install cloudflared")
    else:
        print("   sudo apt-get install cloudflared   OR   brew install cloudflared")
    return ""


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url.rstrip("/")


def main():
    parser = argparse.ArgumentParser(description="Start global HTTPS tunnel for Ssense SLM Server")
    parser.add_argument("--port", type=int, default=8000, help="Local server port (default: 8000)")
    parser.add_argument("--token", type=str, default=os.getenv("CLOUDFLARE_TUNNEL_TOKEN", ""), help="Cloudflare Zero Trust token (optional)")
    parser.add_argument("--domain", type=str, default=os.getenv("CLOUDFLARE_DOMAIN", ""), help="Custom domain / public endpoint (e.g., api.yourdomain.com or https://slm.yourdomain.com)")
    parser.add_argument("--no-build", action="store_true", help="Skip automatic extension rebuild after domain sync")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    server_env = project_root / "apps" / "slm-server" / ".env"
    extension_env = project_root / "apps" / "extension" / ".env.production"
    extension_dev_env = project_root / "apps" / "extension" / ".env"
    root_env = project_root / ".env"

    print("═══════════════════════════════════════════════════════════════════")
    print("🚀 Ssense Global Tunnel & Domain Synchronizer")
    print("═══════════════════════════════════════════════════════════════════")

    custom_domain = normalize_url(args.domain)
    # Check if a custom domain was previously configured in server .env (not trycloudflare.com)
    if not custom_domain and server_env.exists():
        for line in server_env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SSENSE_PUBLIC_URL=") and "trycloudflare.com" not in line:
                val = line.split("=", 1)[1].strip()
                if val:
                    custom_domain = normalize_url(val)
                    print(f"📌 Detected existing specified domain from server .env: {custom_domain}")
                    break

    cloudflared = find_or_download_cloudflared()
    if not cloudflared:
        print("\n❌ Could not locate cloudflared binary. Please install cloudflared to start tunnel.")
        sys.exit(1)

    cmd = [cloudflared, "tunnel", "--no-autoupdate"]
    if args.token:
        cmd.extend(["run", "--token", args.token])
        print(f"🔒 Starting named tunnel with Cloudflare Zero Trust token...")
    else:
        cmd.extend(["--url", f"http://127.0.0.1:{args.port}"])
        if custom_domain:
            print(f"🌐 Starting tunnel for specified endpoint: {custom_domain} (forwarding to port {args.port})...")
        else:
            print(f"🌐 Starting Quick Tunnel on port {args.port} (free, no domain needed)...")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    tunnel_url = None
    if custom_domain:
        # User explicitly specified a permanent domain / proper endpoint
        tunnel_url = custom_domain
        print(f"\n🎯 Using specified domain endpoint: {tunnel_url}")
    else:
        url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        print("⏳ Waiting for public tunnel domain assignment...")
        start_time = time.time()

        while time.time() - start_time < 30:
            line = proc.stdout.readline()
            if not line:
                break
            match = url_pattern.search(line)
            if match:
                tunnel_url = match.group(0)
                break

    if not tunnel_url:
        print("⚠️  Could not automatically extract tunnel URL from output.")
        print("   If you are using a custom domain token, specify --domain or set SSENSE_PUBLIC_URL directly.")
    else:
        print("\n" + "=" * 65)
        print(f"🎉 TUNNEL ACTIVE: {tunnel_url}")
        print("=" * 65 + "\n")

        print("📝 Updating server and extension environment variables...")
        update_env_file(server_env, "SSENSE_PUBLIC_URL", tunnel_url)
        print(f"   ✅ Server .env updated with SSENSE_PUBLIC_URL={tunnel_url}")

        update_env_file(extension_env, "VITE_SSENSE_SERVER_URL", tunnel_url)
        print(f"   ✅ Extension .env.production updated with VITE_SSENSE_SERVER_URL={tunnel_url}")

        if extension_dev_env.exists():
            update_env_file(extension_dev_env, "VITE_SSENSE_SERVER_URL", tunnel_url)
            print(f"   ✅ Extension .env updated with VITE_SSENSE_SERVER_URL={tunnel_url}")

        if root_env.exists():
            update_env_file(root_env, "VITE_SSENSE_SERVER_URL", tunnel_url)
            print(f"   ✅ Root .env updated with VITE_SSENSE_SERVER_URL={tunnel_url}")

        if not args.no_build:
            print("\n🔨 Building extension with the synchronized endpoint...")
            try:
                npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
                subprocess.run(
                    [npm_cmd, "run", "build"],
                    cwd=str(project_root / "apps" / "extension"),
                    check=True,
                    shell=(sys.platform == "win32"),
                )
                print("   ✅ Extension built successfully in apps/extension/dist!")
            except Exception as e:
                print(f"   ⚠️  Extension build failed or npm not in PATH: {e}")

        print("\n💡 What to do next:")
        print("   1. Keep this tunnel process running on your AGX Spark / lab machine.")
        print(f"   2. Connect to proper endpoint: {tunnel_url}/v1/health")
        print("   3. Install the extension on any laptop anywhere in the world.")
        print("   4. The extension is now pre-configured to connect over HTTPS!")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping tunnel...")
        proc.terminate()


if __name__ == "__main__":
    main()
