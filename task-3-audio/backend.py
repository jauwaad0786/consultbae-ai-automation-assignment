"""
backend.py — Task 3: Mini Audio Collection App (backend logic)

Responsibilities:
  - MySQL connection (same DB as Task 1's `people` master table)
  - Creates `submissions` table if it doesn't exist
  - Saves uploaded/recorded audio to /audio_storage/<uuid>.<ext>
  - Extracts duration, sample rate, bitrate, loudness (dB) + a rough
    noise/quality estimate (bonus) using pydub (needs ffmpeg installed)
  - Matches submitter to an existing `people` row by phone, else creates one
  - Insert / fetch submissions for the list view

Env vars (set these before running, or export in your shell):
  DB_HOST      default: localhost
  DB_USER      default: root
  DB_PASSWORD  default: "" (empty)
  DB_NAME      default: consultbae
"""

import os
import re
import uuid
import numpy as np
import pymysql
from pydub import AudioSegment
from dotenv import load_dotenv

# Loads variables from a `.env` file (in the same folder) into os.environ.
# If .env doesn't exist, this just silently does nothing.
load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "consultbae"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_storage")
os.makedirs(AUDIO_DIR, exist_ok=True)


def get_conn():
    """Fresh pymysql connection. Called per-operation (Streamlit reruns a lot)."""
    return pymysql.connect(**DB_CONFIG)


# ---------------------------------------------------------------------------
# Schema bootstrap — matches the people(person_id) master table from Task 1
# ---------------------------------------------------------------------------
def init_db():
    ddl = """
    CREATE TABLE IF NOT EXISTS submissions (
        submission_id   INT AUTO_INCREMENT PRIMARY KEY,
        person_id       INT NULL,
        name            VARCHAR(255) NOT NULL,
        phone           VARCHAR(20)  NOT NULL,
        audio_path      VARCHAR(500) NOT NULL,
        duration_sec    FLOAT,
        sample_rate_hz  INT,
        bitrate_kbps    FLOAT,
        loudness_db     FLOAT,
        noise_estimate  VARCHAR(20),
        snr_db          FLOAT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES people(person_id)
            ON DELETE SET NULL
    );
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phone normalization (same rule as Task 1 pipeline — keep it consistent)
# ---------------------------------------------------------------------------
def normalize_phone(raw_phone: str) -> str:
    digits = re.sub(r"\D", "", raw_phone or "")
    if len(digits) > 10:
        digits = digits[-10:]  # strip leading 91 / 0 / +91 etc.
    return digits


def find_or_create_person(name: str, phone: str) -> int:
    """Match against Task 1's `people` table by canonical phone.
    If no match, create a minimal person row so the FK always resolves."""
    canonical_phone = normalize_phone(phone)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT person_id FROM people WHERE canonical_phone = %s LIMIT 1",
                (canonical_phone,),
            )
            row = cur.fetchone()
            if row:
                return row["person_id"]

            cur.execute(
                """INSERT INTO people (full_name, canonical_phone, source_flags, status)
                   VALUES (%s, %s, %s, %s)""",
                (name.strip(), canonical_phone, "audio_app", "new"),
            )
            return cur.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Audio storage
# ---------------------------------------------------------------------------
def save_audio_file(uploaded_bytes: bytes, original_filename: str) -> str:
    """Saves raw bytes as-is (webm/wav/mp3/whatever the browser gives us)
    and returns the absolute path. Extension preserved for pydub/ffmpeg
    to auto-detect the container format."""
    ext = os.path.splitext(original_filename)[1] or ".wav"
    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(AUDIO_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(uploaded_bytes)
    return fpath


# ---------------------------------------------------------------------------
# Audio property extraction
# ---------------------------------------------------------------------------
def extract_audio_properties(filepath: str) -> dict:
    """duration, sample rate, bitrate, loudness + a rough SNR-based
    noise/quality estimate. Uses pydub -> ffmpeg, so it works on
    webm/ogg/mp3/wav regardless of what the browser recorded."""
    audio = AudioSegment.from_file(filepath)

    duration_sec = len(audio) / 1000.0
    sample_rate_hz = audio.frame_rate
    loudness_db = audio.dBFS  # average loudness (negative dBFS, 0 = max)

    file_size_bytes = os.path.getsize(filepath)
    bitrate_kbps = (
        round((file_size_bytes * 8 / 1000) / duration_sec, 1) if duration_sec > 0 else 0.0
    )

    # --- Bonus: rough noise/quality estimate via chunked RMS (SNR proxy) ---
    chunk_ms = 100
    chunk_dbfs = []
    for i in range(0, len(audio), chunk_ms):
        chunk = audio[i : i + chunk_ms]
        if chunk.rms > 0:
            chunk_dbfs.append(chunk.dBFS)

    if len(chunk_dbfs) >= 5:
        arr = np.array(chunk_dbfs)
        noise_floor = np.percentile(arr, 5)   # quietest parts ≈ background noise
        peak = np.percentile(arr, 95)         # loudest parts ≈ speech
        snr_db = round(float(peak - noise_floor), 1)
    else:
        snr_db = 0.0

    if snr_db >= 20:
        noise_estimate = "clean"
    elif snr_db >= 10:
        noise_estimate = "moderate"
    else:
        noise_estimate = "noisy"

    return {
        "duration_sec": round(duration_sec, 2),
        "sample_rate_hz": sample_rate_hz,
        "bitrate_kbps": bitrate_kbps,
        "loudness_db": round(loudness_db, 1) if loudness_db != float("-inf") else -96.0,
        "noise_estimate": noise_estimate,
        "snr_db": snr_db,
    }


# ---------------------------------------------------------------------------
# Submission CRUD
# ---------------------------------------------------------------------------
def insert_submission(person_id, name, phone, audio_path, props: dict) -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO submissions
                   (person_id, name, phone, audio_path, duration_sec,
                    sample_rate_hz, bitrate_kbps, loudness_db, noise_estimate, snr_db)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    person_id, name.strip(), phone.strip(), audio_path,
                    props["duration_sec"], props["sample_rate_hz"],
                    props["bitrate_kbps"], props["loudness_db"],
                    props["noise_estimate"], props["snr_db"],
                ),
            )
            return cur.lastrowid
    finally:
        conn.close()


def get_all_submissions() -> list:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT submission_id, person_id, name, phone, audio_path,
                          duration_sec, sample_rate_hz, bitrate_kbps,
                          loudness_db, noise_estimate, snr_db, created_at
                   FROM submissions ORDER BY created_at DESC"""
            )
            return cur.fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# One-shot pipeline used by the frontend on form submit
# ---------------------------------------------------------------------------
def process_submission(name: str, phone: str, audio_bytes: bytes, original_filename: str) -> dict:
    """Full flow: save file -> extract properties -> match/create person -> insert row."""
    audio_path = save_audio_file(audio_bytes, original_filename)
    props = extract_audio_properties(audio_path)
    person_id = find_or_create_person(name, phone)
    submission_id = insert_submission(person_id, name, phone, audio_path, props)
    return {"submission_id": submission_id, "person_id": person_id, "audio_path": audio_path, **props}


if __name__ == "__main__":
    init_db()
    print(f"submissions table ready. Audio files will be stored in: {AUDIO_DIR}")
