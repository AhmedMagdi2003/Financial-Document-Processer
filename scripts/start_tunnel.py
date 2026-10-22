"""Script to run or detect ngrok tunnel, update .env with the public URL,
and display ready-to-copy integration parameters.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def get_active_ngrok_url():
    """Query local ngrok API at http://127.0.0.1:4040/api/tunnels."""
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel.get("public_url")
                if "public_url" in tunnel and tunnel["public_url"].startswith("https://"):
                    return tunnel["public_url"]
    except Exception:
        return None
    return None


def update_env_file(ngrok_url):
    """Update NGROK_URL and HOSTING_PROVIDER in .env."""
    if not ENV_PATH.exists():
        print(f"Warning: {ENV_PATH} not found.")
        return

    content = ENV_PATH.read_text(encoding="utf-8")
    
    # Update HOSTING_PROVIDER
    if "HOSTING_PROVIDER=" in content:
        content = re.sub(r"HOSTING_PROVIDER=.*", "HOSTING_PROVIDER=ngrok", content)
    else:
        content += "\nHOSTING_PROVIDER=ngrok"

    # Update NGROK_URL
    if "NGROK_URL=" in content:
        content = re.sub(r"NGROK_URL=.*", f"NGROK_URL={ngrok_url}", content)
    else:
        content += f"\nNGROK_URL={ngrok_url}"

    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"[OK] Updated .env with HOSTING_PROVIDER=ngrok and NGROK_URL={ngrok_url}")


def main():
    print("=" * 60)
    print("  Impact Financial Document Processor - ngrok Tunnel Helper")
    print("=" * 60)

    # 1. Check if ngrok is already running
    active_url = get_active_ngrok_url()
    if active_url:
        print(f"\n[FOUND] An active ngrok tunnel is already running at:")
        print(f"        {active_url}")
        update_env_file(active_url)
        print_instructions(active_url)
        return

    # 2. Check if ngrok binary is installed
    ngrok_bin = shutil.which("ngrok")
    if not ngrok_bin:
        print("\n[ERROR] 'ngrok' was not found on your system PATH.")
        print("To install ngrok on Windows:")
        print("  1. Download from https://ngrok.com/download OR run:")
        print("     winget install ngrok.ngrok")
        print("  2. Connect your free ngrok account token:")
        print("     ngrok config add-authtoken <YOUR_TOKEN>")
        print("  3. Run: ngrok http 8000")
        return

    print("\nStarting ngrok tunnel on port 8000...")
    proc = subprocess.Popen([ngrok_bin, "http", "8000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for tunnel API to be ready
    retries = 15
    while retries > 0:
        time.sleep(1)
        active_url = get_active_ngrok_url()
        if active_url:
            break
        retries -= 1

    if not active_url:
        print("\n[ERROR] Timed out waiting for ngrok tunnel to start.")
        print("Try running manually in a separate terminal: ngrok http 8000")
        return

    print(f"\n[SUCCESS] ngrok tunnel is live at:")
    print(f"          {active_url}")
    update_env_file(active_url)
    print_instructions(active_url)

    print("\nPress Ctrl+C to stop tunnel...")
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping ngrok...")
        proc.terminate()


def print_instructions(public_url):
    print("\n" + "-" * 60)
    print("  READY-TO-USE INTEGRATION ENDPOINTS:")
    print("-" * 60)
    print(f"  * Public Base URL : {public_url}")
    print(f"  * Upload Endpoint : {public_url}/api/v1/documents")
    print(f"  * Projects List   : {public_url}/api/v1/projects")
    print("-" * 60)
    print("\nCopy these values into your Google Apps Script Properties or Make.com scenario:")
    print(f"  API_BASE_URL = {public_url}")
    print("-" * 60)


if __name__ == "__main__":
    main()
