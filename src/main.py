import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import requests
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

DATA_DIR = Path("/app/data")
STATE_FILE = DATA_DIR / "version_state.json"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "3600"))
GOOGLE_CHAT_WEBHOOK_URL = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()

CHROME_API = "https://omahaproxy.appspot.com/all.json"  # alternative: versionhistory.googleapis.com
EDGE_API = "https://edgeupdates.microsoft.com/api/products?view=stable"

# Download pages (not direct installers for all cases) - provide standard stable channel links.
CHROME_DL_PAGE = "https://www.google.com/chrome/"
EDGE_DL_PAGE = "https://www.microsoft.com/edge"

lock = threading.Lock()


def log(level: str, msg: str):
    levels = ["debug", "info", "warn", "error"]
    if level not in levels:
        level = "info"
    if levels.index(level) >= levels.index(LOG_LEVEL):
        print(f"[{datetime.utcnow().isoformat()}Z] {level.upper()}: {msg}",
              flush=True)


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log("error", f"Failed to read state file: {e}")
    return {
        "chrome": {
            "version": None,
            "last_checked": None
        },
        "edge": {
            "version": None,
            "last_checked": None
        },
        "history": []  # list of events
    }


def save_state(state: Dict[str, Any]):
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    except Exception as e:
        log("error", f"Failed to write state file: {e}")


def fetch_chrome_version() -> str:
    # Parse omahaproxy JSON for stable Windows
    r = requests.get(CHROME_API, timeout=20)
    r.raise_for_status()
    data = r.json()
    for item in data:
        if item.get("os") == "win" and item.get("channel") == "stable":
            return item.get("current_version")
    raise RuntimeError("Chrome stable version not found in response")


def fetch_edge_version() -> str:
    r = requests.get(EDGE_API, timeout=20)
    r.raise_for_status()
    data = r.json()
    # Find Stable channel product 'Stable'
    versions = []
    for product in data:
        if product.get("Product") == "Stable":
            for release in product.get("Releases", []):
                v = release.get("ProductVersion")
                if v:
                    versions.append(v)
    if not versions:
        raise RuntimeError("No Edge stable versions found")
    # Choose the latest lexicographically (versions are numeric dot separated); sort by tuple of ints
    versions_sorted = sorted(versions,
                             key=lambda s: [int(p) for p in s.split('.')])
    return versions_sorted[-1]


def send_google_chat_notification(title: str, text: str):
    if not GOOGLE_CHAT_WEBHOOK_URL:
        log("info", "GOOGLE_CHAT_WEBHOOK_URL not set; skip notification")
        return
    body = {"text": f"{title}\n{text}"}
    try:
        resp = requests.post(GOOGLE_CHAT_WEBHOOK_URL, json=body, timeout=10)
        if resp.status_code >= 300:
            log("error",
                f"Google Chat webhook failed: {resp.status_code} {resp.text}")
    except Exception as e:
        log("error", f"Google Chat notification error: {e}")


def record_event(state: Dict[str, Any], browser: str, old: str, new: str):
    event = {
        "browser": browser,
        "old": old,
        "new": new,
        "timestamp":
        datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    }
    state.setdefault("history", []).append(event)


def check_versions_once() -> Dict[str, Any]:
    updated = []
    with lock:
        state = load_state()
        # Chrome
        try:
            chrome_version = fetch_chrome_version()
            old_chrome = state["chrome"].get("version")
            state["chrome"].update({
                "version":
                chrome_version,
                "last_checked":
                datetime.utcnow().isoformat() + 'Z'
            })
            if chrome_version and chrome_version != old_chrome and old_chrome is not None:
                record_event(state, "chrome", old_chrome, chrome_version)
                updated.append(
                    ("Chrome", old_chrome, chrome_version, CHROME_DL_PAGE))
        except Exception as e:
            log("error", f"Chrome version check failed: {e}")

        # Edge
        try:
            edge_version = fetch_edge_version()
            old_edge = state["edge"].get("version")
            state["edge"].update({
                "version":
                edge_version,
                "last_checked":
                datetime.utcnow().isoformat() + 'Z'
            })
            if edge_version and edge_version != old_edge and old_edge is not None:
                record_event(state, "edge", old_edge, edge_version)
                updated.append(("Edge", old_edge, edge_version, EDGE_DL_PAGE))
        except Exception as e:
            log("error", f"Edge version check failed: {e}")

        save_state(state)

    # Notifications outside lock
    for (name, old_v, new_v, url) in updated:
        send_google_chat_notification(
            f"{name} 新バージョン検出: {new_v}",
            f"旧: {old_v} -> 新: {new_v}\nダウンロード: {url}")

    return state


def loop_check_versions(stop_event: threading.Event):
    log("info",
        f"Start background version check loop interval={CHECK_INTERVAL}s")
    # First run immediately to populate state
    try:
        check_versions_once()
    except Exception as e:
        log("error", f"Initial version check failed: {e}")
    while not stop_event.wait(CHECK_INTERVAL):
        try:
            check_versions_once()
        except Exception as e:
            log("error", f"Periodic version check failed: {e}")


app = FastAPI(title="Browser Update Controller", version="0.1.0")
stop_event = threading.Event()
thread: threading.Thread | None = None


class VersionsResponse(BaseModel):
    chrome: Dict[str, Any]
    edge: Dict[str, Any]
    history: list


@app.on_event("startup")
def on_startup():
    global thread
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Ensure state file exists
    with lock:
        if not STATE_FILE.exists():
            save_state(load_state())
    thread = threading.Thread(target=loop_check_versions,
                              args=(stop_event, ),
                              daemon=True)
    thread.start()


@app.on_event("shutdown")
def on_shutdown():
    stop_event.set()
    if thread:
        thread.join(timeout=5)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/versions", response_model=VersionsResponse)
def get_versions():
    with lock:
        state = load_state()
    return state


@app.post("/refresh", response_model=VersionsResponse)
def refresh_versions(background_tasks: BackgroundTasks):
    # Run immediately in background to avoid long blocking if network slow
    background_tasks.add_task(check_versions_once)
    with lock:
        state = load_state()
    return state


@app.get("/download/chrome")
def download_chrome():
    return {"download_page": CHROME_DL_PAGE}


@app.get("/download/edge")
def download_edge():
    return {"download_page": EDGE_DL_PAGE}


@app.get("/")
def root():
    return {
        "message":
        "Browser Update Controller",
        "endpoints": [
            "/health", "/versions", "/refresh", "/download/chrome",
            "/download/edge"
        ]
    }
