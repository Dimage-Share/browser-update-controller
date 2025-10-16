import os, logging
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from .database import init_db, SessionLocal, Report
from .models import ReportIn
from .config_manager import config_state
from .scheduler import init_scheduler
from .googlechat import chat_send

PORT = int(os.getenv("CONTROLLER_PORT", "6001"))
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
AUTO_CHECK_INTERVAL_MIN = int(os.getenv("AUTO_CHECK_INTERVAL_MIN", "180"))

app = FastAPI(title="Browser Update Controller")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
async def startup():
    logging.basicConfig(level=logging.INFO)
    init_db()
    init_scheduler()
    logging.info("Browser Update Controller started")


@app.get("/healthz")
async def health():
    return {"ok": True}


SUPPORTED_BROWSERS = {"chrome", "edge"}
SUPPORTED_RINGS = {"fast", "stable"}


@app.get("/config/{browser}/{ring}.json")
async def get_config(browser: str, ring: str):
    if browser not in SUPPORTED_BROWSERS or ring not in SUPPORTED_RINGS:
        raise HTTPException(404, "Not found")
    cfg = await config_state.build_config(browser, ring,
                                          AUTO_CHECK_INTERVAL_MIN)
    return JSONResponse(cfg)


def verify(token, admin=False):
    if admin:
        if token != ADMIN_TOKEN:
            raise HTTPException(403, "Forbidden")
    else:
        if token != AUTH_TOKEN:
            raise HTTPException(403, "Forbidden")


@app.post("/report")
async def report(data: ReportIn,
                 x_auth_token: str = Header(None),
                 db: Session = Depends(get_db)):
    verify(x_auth_token)
    if data.browser not in SUPPORTED_BROWSERS:
        raise HTTPException(400, "Unsupported browser")
    rec = Report(browser=data.browser,
                 hostname=data.hostname,
                 os=data.os,
                 ring=data.ring,
                 version=data.version,
                 status=data.status,
                 details=data.details)
    db.add(rec)
    db.commit()
    if data.status in ("OUTDATED", "WARNING", "MISSING",
                       "BLOCKED_WAIT_PREFIX"):
        await chat_send(
            f":warning: [{data.browser}] {data.hostname} {data.version} {data.status} ({data.ring})"
        )
    return {"stored": True}


@app.post("/approve")
async def approve(body: dict, x_admin_token: str = Header(None)):
    verify(x_admin_token, admin=True)
    browser = body.get("browser")
    major = body.get("major")
    if browser not in SUPPORTED_BROWSERS or not isinstance(major, int):
        raise HTTPException(400, "Invalid")
    changed = config_state.approve(browser, major)
    if changed:
        await chat_send(
            f":white_check_mark: Approved {browser} stable major -> {major}")
        return {"message": "Approved", "browser": browser, "major": major}
    return {"message": "No change", "browser": browser, "major": major}


@app.get("/stats")
async def stats(db: Session = Depends(get_db)):
    rows = db.query(Report).all()
    agg = {}
    for r in rows:
        agg.setdefault(r.browser, {}).setdefault(r.ring,
                                                 {}).setdefault(r.status, 0)
        agg[r.browser][r.ring][r.status] += 1
    return agg


@app.get("/dashboard")
async def dashboard(db: Session = Depends(get_db)):
    rows = db.query(Report).order_by(Report.id.desc()).limit(200).all()
    html = [
        "<html><head><title>Browser Dashboard</title></head><body><h2>Recent Reports</h2>",
        "<table border=1><tr><th>time</th><th>browser</th><th>host</th><th>os</th><th>ring</th><th>version</th><th>status</th></tr>"
    ]
    for r in rows:
        html.append(
            f"<tr><td>{r.created_at}</td><td>{r.browser}</td><td>{r.hostname}</td>"
            f"<td>{r.os}</td><td>{r.ring}</td><td>{r.version}</td><td>{r.status}</td></tr>"
        )
    html.append("</table></body></html>")
    return HTMLResponse("\n".join(html))
