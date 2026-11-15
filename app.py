from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import csv
import io
import random
import sqlite3
import os
import hmac
import hashlib
import base64
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "spacecare.db"


# ---------------- ADMIN LOGIN SETTINGS ----------------

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "SpaceCare@123"
SECRET_KEY = "SpaceCare-Secret-Key-2026"
COOKIE_NAME = "spacecare_session"
SESSION_DURATION = 8 * 60 * 60


def create_token(username):
    expiry = int(time.time()) + SESSION_DURATION
    payload = f"{username}:{expiry}".encode()

    signature = hmac.new(
        SECRET_KEY.encode(),
        payload,
        hashlib.sha256
    ).hexdigest().encode()

    token_data = payload + b"." + signature

    return base64.urlsafe_b64encode(token_data).decode()


def verify_token(token):
    try:
        token_data = base64.urlsafe_b64decode(token.encode())
        payload, signature = token_data.rsplit(b".", 1)

        expected_signature = hmac.new(
            SECRET_KEY.encode(),
            payload,
            hashlib.sha256
        ).hexdigest().encode()

        if not hmac.compare_digest(signature, expected_signature):
            return False

        username, expiry = payload.decode().rsplit(":", 1)

        if username != ADMIN_USERNAME:
            return False

        if int(expiry) < int(time.time()):
            return False

        return True

    except Exception:
        return False


# ---------------- ASTRONAUT DATA ----------------

DEMO_ASTRONAUTS = [
    ("AST001", "Alex Carter", "Artemis-III", "Orion", 38),
    ("AST002", "Sarah Wilson", "Artemis-III", "Orion", 34),
    ("AST003", "John Miller", "Ares-Next", "Horizon", 41),
    ("AST004", "Maya Patel", "Ares-Next", "Horizon", 32),
    ("AST005", "Daniel Kim", "Lunar Gateway", "Gateway", 36),
]


thresholds = {
    "heart_rate_low": 50,
    "heart_rate_high": 100,
    "spo2_low": 95,
    "temperature_high": 38.0,
    "systolic_high": 140,
    "respiratory_high": 24
}

clients = []
scenarios = {}


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with get_db() as conn:

        conn.execute("""
        CREATE TABLE IF NOT EXISTS astronauts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mission TEXT,
            spacecraft TEXT,
            age INTEGER,
            active INTEGER DEFAULT 1
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            astronaut_id TEXT,
            timestamp TEXT,
            heart_rate INTEGER,
            spo2 INTEGER,
            temperature REAL,
            systolic_bp INTEGER,
            diastolic_bp INTEGER,
            respiratory_rate INTEGER,
            activity INTEGER,
            sleep_hours REAL,
            stress INTEGER
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            astronaut_id TEXT,
            astronaut_name TEXT,
            parameter TEXT,
            value TEXT,
            severity TEXT,
            description TEXT,
            timestamp TEXT,
            acknowledged INTEGER DEFAULT 0
        )
        """)

        count = conn.execute(
            "SELECT COUNT(*) FROM astronauts"
        ).fetchone()[0]

        if count == 0:
            conn.executemany("""
            INSERT INTO astronauts
            (id, name, mission, spacecraft, age)
            VALUES (?, ?, ?, ?, ?)
            """, DEMO_ASTRONAUTS)


def get_astronauts():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM astronauts WHERE active=1 ORDER BY id"
        ).fetchall()

        return [dict(row) for row in rows]


# ---------------- SENSOR SIMULATION ----------------

def create_reading(person):

    scenario = scenarios.get(person["id"], "normal")

    reading = {
        "astronaut_id": person["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "heart_rate": random.randint(65, 95),
        "spo2": random.randint(96, 100),
        "temperature": round(random.uniform(36.3, 37.4), 1),
        "systolic_bp": random.randint(108, 128),
        "diastolic_bp": random.randint(68, 84),
        "respiratory_rate": random.randint(12, 20),
        "activity": random.randint(1000, 9000),
        "sleep_hours": round(random.uniform(5.5, 8.5), 1),
        "stress": random.randint(10, 55)
    }

    if scenario == "high_heart_rate":
        reading["heart_rate"] = random.randint(115, 145)

    elif scenario == "low_spo2":
        reading["spo2"] = random.randint(85, 92)

    elif scenario == "fever":
        reading["temperature"] = round(
            random.uniform(38.2, 39.2), 1
        )

    elif scenario == "critical":
        reading["heart_rate"] = 145
        reading["spo2"] = 88
        reading["temperature"] = 39.0

    return reading


def save_reading(r):

    with get_db() as conn:
        conn.execute("""
        INSERT INTO readings (
            astronaut_id, timestamp, heart_rate, spo2,
            temperature, systolic_bp, diastolic_bp,
            respiratory_rate, activity, sleep_hours, stress
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["astronaut_id"],
            r["timestamp"],
            r["heart_rate"],
            r["spo2"],
            r["temperature"],
            r["systolic_bp"],
            r["diastolic_bp"],
            r["respiratory_rate"],
            r["activity"],
            r["sleep_hours"],
            r["stress"]
        ))


# ---------------- ALERT SYSTEM ----------------

def check_alerts(person, r):

    checks = [
        ("Heart rate", r["heart_rate"] > thresholds["heart_rate_high"],
         "ORANGE", "High heart rate"),

        ("Heart rate", r["heart_rate"] < thresholds["heart_rate_low"],
         "YELLOW", "Low heart rate"),

        ("SpO2", r["spo2"] < thresholds["spo2_low"],
         "RED", "Low oxygen saturation"),

        ("Temperature", r["temperature"] > thresholds["temperature_high"],
         "ORANGE", "High body temperature"),

        ("Blood pressure", r["systolic_bp"] > thresholds["systolic_high"],
         "ORANGE", "High systolic blood pressure"),

        ("Respiratory rate",
         r["respiratory_rate"] > thresholds["respiratory_high"],
         "YELLOW", "High respiratory rate")
    ]

    created = []

    with get_db() as conn:

        for parameter, triggered, severity, description in checks:

            if not triggered:
                continue

            recent = conn.execute("""
                SELECT id FROM alerts
                WHERE astronaut_id=? AND parameter=?
                AND acknowledged=0
                AND datetime(timestamp) > datetime('now','-1 minute')
            """, (person["id"], parameter)).fetchone()

            if recent:
                continue

            values = {
                "Heart rate": r["heart_rate"],
                "SpO2": r["spo2"],
                "Temperature": r["temperature"],
                "Blood pressure": r["systolic_bp"],
                "Respiratory rate": r["respiratory_rate"]
            }

            cur = conn.execute("""
                INSERT INTO alerts
                (astronaut_id, astronaut_name, parameter, value,
                 severity, description, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                person["id"],
                person["name"],
                parameter,
                str(values[parameter]),
                severity,
                description,
                r["timestamp"]
            ))

            created.append({
                "id": cur.lastrowid,
                "astronaut_id": person["id"],
                "astronaut_name": person["name"],
                "parameter": parameter,
                "value": str(values[parameter]),
                "severity": severity,
                "description": description,
                "timestamp": r["timestamp"],
                "acknowledged": 0
            })

    return created


# ---------------- WEBSOCKET BROADCAST ----------------

async def broadcast(data):

    disconnected = []

    for client in clients:
        try:
            await client.send_json(data)

        except Exception:
            disconnected.append(client)

    for client in disconnected:
        if client in clients:
            clients.remove(client)


# ---------------- SENSOR BACKGROUND TASK ----------------

async def sensor_simulator():

    while True:

        for person in get_astronauts():

            if scenarios.get(person["id"]) == "offline":
                continue

            reading = create_reading(person)
            save_reading(reading)

            alerts = check_alerts(person, reading)

            await broadcast({
                "type": "reading",
                "reading": reading,
                "alerts": alerts
            })

        await asyncio.sleep(2)


# ---------------- APPLICATION STARTUP ----------------

@asynccontextmanager
async def lifespan(app):

    initialize_database()

    task = asyncio.create_task(sensor_simulator())

    yield

    task.cancel()

    try:
        await task

    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="SpaceCare Astronaut Health Monitoring",
    version="1.0.0",
    lifespan=lifespan
)


# ---------------- LOGIN SECURITY MIDDLEWARE ----------------

@app.middleware("http")
async def admin_authentication(request: Request, call_next):

    path = request.url.path
    token = request.cookies.get(COOKIE_NAME)

    authenticated = bool(token and verify_token(token))

    if path.startswith("/api/") and path != "/api/login":

        if not authenticated:
            return JSONResponse(
                status_code=401,
                content={"detail": "Please login as admin"}
            )

    if path == "/static/index.html" and not authenticated:

        return FileResponse(
            BASE_DIR / "static" / "login.html"
        )

    return await call_next(request)


# ---------------- STATIC FILES ----------------

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)


# ---------------- HOME PAGE ----------------

@app.get("/")
async def home(request: Request):

    token = request.cookies.get(COOKIE_NAME)

    if token and verify_token(token):

        return FileResponse(
            BASE_DIR / "static" / "index.html"
        )

    return FileResponse(
        BASE_DIR / "static" / "login.html"
    )


# ---------------- HEALTH API ----------------

@app.get("/api/health")
async def health():

    return {
        "status": "online",
        "data_mode": "SIMULATED"
    }


# ---------------- ASTRONAUT API ----------------

@app.get("/api/astronauts")
async def astronauts():

    return get_astronauts()


class AstronautCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    mission: str = Field(default="Unassigned", max_length=100)
    spacecraft: str = Field(default="Unassigned", max_length=100)
    age: int = Field(default=30, ge=18, le=100)


@app.post("/api/astronauts")
async def create_astronaut(data: AstronautCreateRequest):
    astro_id = data.id.strip().upper()
    name = data.name.strip()
    mission = data.mission.strip() or "Unassigned"
    spacecraft = data.spacecraft.strip() or "Unassigned"
    age = data.age

    if not astro_id or not name:
        raise HTTPException(
            status_code=400,
            detail="Astronaut ID and Name are required"
        )

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM astronauts WHERE id=?", (astro_id,)
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Astronaut with ID '{astro_id}' already exists"
            )

        conn.execute("""
            INSERT INTO astronauts (id, name, mission, spacecraft, age, active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (astro_id, name, mission, spacecraft, age))

    return {
        "message": "Astronaut created successfully",
        "astronaut": {
            "id": astro_id,
            "name": name,
            "mission": mission,
            "spacecraft": spacecraft,
            "age": age,
            "active": 1
        }
    }


class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
async def admin_login(data: LoginRequest):

    username = data.username.strip()

    valid_username = hmac.compare_digest(
        username,
        ADMIN_USERNAME
    )

    valid_password = hmac.compare_digest(
        data.password,
        ADMIN_PASSWORD
    )

    if not valid_username or not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = create_token(username)

    response = JSONResponse(
        content={"message": "Login successful"}
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=SESSION_DURATION
    )

    return response


# ---------------- SUMMARY API ----------------

@app.get("/api/summary")
async def summary():

    crew = get_astronauts()

    with get_db() as conn:

        alert_count = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE acknowledged=0"
        ).fetchone()[0]

        readings = []

        for person in crew:

            row = conn.execute("""
                SELECT * FROM readings
                WHERE astronaut_id=?
                ORDER BY id DESC LIMIT 1
            """, (person["id"],)).fetchone()

            if row:
                readings.append(dict(row))

    return {
        "astronauts": len(crew),
        "open_alerts": alert_count,
        "latest": readings,
        "data_mode": "SIMULATED"
    }


# ---------------- ALERT API ----------------

@app.get("/api/alerts")
async def get_alerts():

    with get_db() as conn:

        rows = conn.execute("""
            SELECT * FROM alerts
            ORDER BY id DESC LIMIT 100
        """).fetchall()

    return [dict(row) for row in rows]


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):

    with get_db() as conn:

        result = conn.execute(
            "UPDATE alerts SET acknowledged=1 WHERE id=?",
            (alert_id,)
        )

        if result.rowcount == 0:
            raise HTTPException(404, "Alert not found")

    return {"message": "Alert acknowledged"}


# ---------------- HISTORY API ----------------

@app.get("/api/history/{astronaut_id}")
async def history(astronaut_id: str, limit: int = 100):

    with get_db() as conn:

        rows = conn.execute("""
            SELECT * FROM readings
            WHERE astronaut_id=?
            ORDER BY id DESC LIMIT ?
        """, (astronaut_id, min(max(limit, 1), 1000))).fetchall()

    return [dict(row) for row in reversed(rows)]


# ---------------- CSV EXPORT API ----------------

@app.get("/api/export/{astronaut_id}.csv")
async def export_csv(astronaut_id: str):

    with get_db() as conn:

        rows = conn.execute("""
            SELECT * FROM readings
            WHERE astronaut_id=?
            ORDER BY id
        """, (astronaut_id,)).fetchall()

    if not rows:
        raise HTTPException(
            404,
            "No readings available yet"
        )

    output = io.StringIO()

    writer = csv.writer(output)
    writer.writerow(rows[0].keys())

    for row in rows:
        writer.writerow(tuple(row))

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename={astronaut_id}_health_report.csv"
        }
    )


# ---------------- SCENARIO API ----------------

class ScenarioRequest(BaseModel):

    scenario: str = Field(
        pattern="^(normal|high_heart_rate|low_spo2|fever|critical|offline)$"
    )


@app.post("/api/astronauts/{astronaut_id}/scenario")
async def set_scenario(astronaut_id: str, data: ScenarioRequest):

    if not any(a["id"] == astronaut_id for a in get_astronauts()):
        raise HTTPException(404, "Astronaut not found")

    scenarios[astronaut_id] = data.scenario

    return {"message": "Scenario updated"}


# ---------------- SETTINGS API ----------------

@app.get("/api/settings")
async def get_settings():

    return thresholds


@app.put("/api/settings")
async def update_settings(data: dict):

    for key in thresholds:

        if key in data:
            thresholds[key] = float(data[key])

    return thresholds


# ---------------- WEBSOCKET ----------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    token = websocket.cookies.get(COOKIE_NAME)

    if not token or not verify_token(token):
        await websocket.close(code=1008)
        return

    await websocket.accept()

    clients.append(websocket)

    try:

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:
        if websocket in clients:
            clients.remove(websocket)




# ---------------- ADMIN LOGOUT API ----------------

@app.post("/api/logout")
async def admin_logout():

    response = JSONResponse(
        content={"message": "Logout successful"}
    )

    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax"
    )

    return response