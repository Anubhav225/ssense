# 🚀 Ssense — Manual Quickstart & Operations Guide

This guide provides step-by-step instructions for **new users** and developers to manually set up, run, and verify all components of the Ssense DPDP Privacy Shield platform:
1. **SLM Backend Server** (FastAPI + Dual-LoRA AI Engine)
2. **Cloudflare Tunnel / Custom Domain Setup** (Named Tunnel with Custom Domain OR Free Quick Tunnel)
3. **Chrome Extension Frontend** (Sidepanel & In-Page Scanner)

---

## 📋 System Prerequisites

| Component | Minimum Requirement | Recommended |
|---|---|---|
| **OS** | Windows 10/11, Ubuntu 22.04+, or macOS 13+ | Linux or Windows WSL2 |
| **Python** | Python 3.10 or 3.11 | Python 3.11 |
| **Node.js** | Node.js v18.x or v20.x + npm | Node.js LTS (v20+) |
| **RAM** | 16 GB System Memory | 32 GB (for local CPU inference) |
| **GPU (Optional)** | NVIDIA GPU with 24GB+ VRAM | RTX 3090/4090 or Jetson Orin |

---

## 🏃 Quick Start Summary (3 Commands)

If you already have your environment ready, run these three terminals:

# Terminal 1 — Start the SLM Server & Cloudflare Tunnel
cd apps/slm-server
# For GPU:
docker compose --profile gpu-tunnel up -d
# (Or use cpu-tunnel / jetson-tunnel)

# Extract your random trycloudflare.com domain:
docker logs ssense-cloudflared-tunnel 2>&1 | grep "trycloudflare.com"

# Terminal 2 — Build the Chrome Extension
cd apps/extension
# (Update VITE_SSENSE_SERVER_URL in .env.production with your Cloudflare domain first!)
npm install && npm run build

Then open `chrome://extensions` in Google Chrome, enable **Developer mode**, and click **Load unpacked** pointing to `apps/extension/dist`.

---

## 🛠️ Step 1: Start the SLM Backend Server

You can run the SLM Server either **directly with Python** (recommended for rapid development and testing) or **via Docker Compose**.

### Method A: Native Python (Fastest — No Docker Build Wait)

1. **Navigate to the server directory**:
   ```bash
   cd apps/slm-server
   ```

2. **Set up the virtual environment**:
   ```bash
   # Create virtual environment if not already created
   python -m venv .venv

   # Activate virtual environment:
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # Windows (cmd):
   .venv\Scripts\activate.bat
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements-cpu.txt
   ```

4. **Initialize Environment Variables**:
   Ensure `apps/slm-server/.env` exists. If not, copy from `.env.example`:
   ```bash
   # Windows PowerShell:
   Copy-Item .env.example .env
   # Linux / macOS:
   cp .env.example .env
   ```

   Generate keys if deploying for production:
   ```bash
   python -c "import secrets; print('SSENSE_API_KEYS=' + secrets.token_urlsafe(32))"
   python -c "import secrets; print('SSENSE_HMAC_SECRET=' + secrets.token_urlsafe(48))"
   ```

5. **Start the FastAPI application**:
   ```bash
   # Windows:
   .venv/Scripts/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

   # Linux / macOS:
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Verify the server is running**:
   Open your browser or run:
   ```bash
   curl http://localhost:8000/health
   # Expected output: {"status":"healthy", ...}
   ```
   Interactive API documentation is available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Method B: Docker Compose (Containerized Production)

If you prefer running inside Docker containers with Redis rate-limiting and Nginx TLS proxy:

1. **Choose your hardware profile**:
   - `cpu` (Standard workstation / laptop, no GPU required)
   - `gpu` (Discrete NVIDIA CUDA GPU, RTX 3090/4090/A100)
   - `jetson` (NVIDIA Jetson AGX Orin / Spark edge boards)

2. **Launch the stack**:
   ```bash
   cd apps/slm-server

   # For CPU:
   docker compose --profile cpu up -d

   # For Discrete NVIDIA GPU:
   docker compose --profile gpu up -d

   # For NVIDIA Jetson:
   docker compose --profile jetson up -d
   ```

3. **Check container health**:
   ```bash
   docker compose ps
   # Verify that ssense-slm-server-* and ssense-redis report (healthy)
   ```

> ⚡ **Docker "Build Once, Start Instantly" Design**:
> - Each profile is tagged with persistent image names (`image: ssense-slm-server:cpu`, `ssense-slm-server:gpu`, `ssense-slm-server:jetson`).
> - After the initial build, running `docker compose --profile <profile> up -d` boots **instantly (< 1 second)** by reusing the existing container image.
> - Source code is bind-mounted directly from the host (`- .:/app:rw`), meaning **any changes to Python code, schemas, or configs take effect immediately without rebuilding Docker**!

---

## 🌐 Step 2: Cloudflare Setup (Global HTTPS Access)

Ssense includes a built-in Docker service for Cloudflare (`ssense-cloudflared-tunnel`) that bridges your local or lab server to the outside world seamlessly.

### Workflow 2.1: Free Quick Tunnel (Zero-Config Development)

If you do **not** have a custom domain and want a free, instant public HTTPS endpoint:

1. **Launch the SLM Server with the Tunnel Profile**:
   ```bash
   cd apps/slm-server
   docker compose --profile gpu-tunnel up -d
   ```
   *(Substitute `gpu-tunnel` with `cpu-tunnel` or `jetson-tunnel` depending on your hardware).*

2. **Extract the Random Domain Name**:
   Cloudflared automatically generates a random `.trycloudflare.com` domain. Find it by viewing the tunnel logs:
   ```bash
   docker logs ssense-cloudflared-tunnel 2>&1 | grep "trycloudflare.com"
   ```
   Copy the URL it gives you (e.g., `https://participated-weighted...trycloudflare.com`).

3. **Synchronize the Extension**:
   Paste this URL as `VITE_SSENSE_SERVER_URL` in `apps/extension/.env.production`, and as `SSENSE_PUBLIC_URL` in `apps/slm-server/.env`.
   Rebuild the extension (`cd apps/extension && npm run build`).

---

### Workflow 2.2: Named Tunnel with a Custom Domain (Production)

If you have a Cloudflare Zero Trust account and want a **permanent, stable custom domain** (e.g. `https://api.yourdomain.com`) without random URL regenerations on restart:

1. **Create a Cloudflare Tunnel**:
   - Go to [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/) > **Networks** > **Tunnels**.
   - Click **Create a Tunnel** > Select **Cloudflared**.
   - Name your tunnel (e.g. `ssense-backend`).
   - Copy the provided **Tunnel Token** (starts with `eyJhIjoi...`).
   - Add a Public Hostname pointing to `localhost:8000`.

2. **Configure `.env`**:
   In `apps/slm-server/.env`, set:
   ```ini
   CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoi...your_cloudflare_token_here...
   SSENSE_PUBLIC_URL=https://api.yourdomain.com
   ```

3. **Launch Docker Stack with Combined Tunnel Profile**:
   ```bash
   docker compose --profile gpu-tunnel up -d
   ```
   *(The Docker container automatically switches to Named Tunnel mode because `CLOUDFLARE_TUNNEL_TOKEN` is present).*

4. **Synchronize the Extension**:
   Set `VITE_SSENSE_SERVER_URL=https://api.yourdomain.com` in `apps/extension/.env.production` and build the extension.

---

### Workflow 2.3: Pure Localhost (No Cloudflare / Offline)

If testing on the same machine without internet access:
1. In `apps/extension/.env` and `apps/extension/.env.production`, verify:
   ```ini
   VITE_SSENSE_SERVER_URL=http://localhost:8000
   ```
2. Build the extension:
   ```bash
   cd apps/extension && npm run build
   ```

### Workflow 2.4: Verifying the Public Connection

You can verify the connection is active by pinging the tunnel's health endpoint over the public internet:
```bash
curl -s https://api.yourdomain.com/health
# Or curl your random trycloudflare.com/health URL
```

---

## 🧩 Step 3: Chrome Extension (Frontend) Setup

### 1. Install Node Dependencies
```bash
cd apps/extension
npm install
```

### 2. Build the Extension
```bash
# Build production bundle into dist/
npm run build
```

*(Optional) For live development with automatic hot reloading on UI file edits:*
```bash
npm run dev
```

### 3. Load the Extension into Google Chrome

1. Open Google Chrome.
2. In the URL address bar, navigate to:
   ```
   chrome://extensions/
   ```
3. In the top-right corner, switch the **Developer mode** toggle to **ON**.
4. In the top-left corner, click the **Load unpacked** button.
5. In the file picker dialog, navigate to your project directory and select:
   ```
   D:\1)MY PROJECTS\ssense\apps\extension\dist
   ```
6. Ssense will appear in your extension list! Click the puzzle icon in Chrome's toolbar and pin **Ssense DPDP Shield**.

---

## ✅ Step 4: Verification & End-to-End Testing

1. **Verify Backend Health**:
   Visit your server endpoint in Chrome:
   - Localhost: `http://localhost:8000/health`
   - Or your Cloudflare domain: `https://api.yourdomain.com/v1/health`
   You should see:
   ```json
   {
     "status": "healthy",
     "compute_profile": "cpu",
     "models_loaded": true
   }
   ```

2. **Test In-Browser Audit**:
   - Navigate to any public website with a privacy policy (e.g., `https://www.wikipedia.org` or `https://www.cloudflare.com`).
   - Click the Ssense extension icon or open the Chrome Sidepanel (`Ctrl+Shift+S` or click the sidepanel icon in Chrome).
   - Ssense will automatically:
     - Detect the privacy policy link.
     - Dispatch the audit request to your SLM server.
     - Display the **DPDP Trust Score (0-100)**, statutory breakdown, XAI feature explanations, and timeline.
     - Enable the interactive legal AI Co-Pilot chat.

---

## 🔧 Common Troubleshooting & FAQ

### Q1: `cloudflared` binary not found
- **Solution**: Install Cloudflare CLI via package manager:
  - Windows: `winget install --id Cloudflare.cloudflared` or `choco install cloudflared`
  - macOS: `brew install cloudflared`
  - Linux: `sudo apt-get install cloudflared`

### Q2: Port 8000 is already in use
- **Solution**: If another process is holding port 8000:
  ```powershell
  # Windows PowerShell:
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
  ```
  ```bash
  # Linux / macOS:
  lsof -ti:8000 | xargs kill -9
  ```

### Q3: Extension shows "Server Disconnected" or "Handshake Failed"
- **Solution**:
  1. Check if the URL in `apps/extension/.env.production` matches the active server or tunnel URL.
  2. If using Quick Tunnel, remember the URL changes whenever the tunnel script is restarted. Re-run `python apps/slm-server/scripts/start_lab_tunnel.py` and rebuild the extension (`npm run build`).
  3. If using a Named Tunnel, ensure your custom domain is active in Cloudflare Zero Trust and configured in `.env`.

### Q4: Extension changes are not reflected in Chrome
- **Solution**:
  1. Run `npm run build` inside `apps/extension`.
  2. Open `chrome://extensions/` and click the **circular refresh icon** on the Ssense extension card.
