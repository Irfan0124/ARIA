
import os
import re
from pathlib import Path
from contextlib import asynccontextmanager
import unicodedata
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse, Response
import tempfile
import threading
from supertonic import TTS
import sqlite3
import json
import asyncio
from faster_whisper import WhisperModel
from fastapi import UploadFile, File
load_dotenv(Path(__file__).with_name(".env"))
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from scipy.signal import resample_poly

OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://127.0.0.1:11434"
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL", "qwen3:4b-instruct"
)

# =========================
# LOCAL SUPERTONIC TTS
# =========================

TTS_VOICE = "F5"
TTS_LANGUAGE = "id"
TTS_SPEED = 1.0

tts_lock = threading.Lock()
def load_supertonic():
    engine = TTS(auto_download=True)
    voice_style = engine.get_voice_style(TTS_VOICE)

    return engine, voice_style

# =========================
# LOCAL FASTER-WHISPER STT
# =========================

STT_MODEL_SIZE = "small"
STT_DEVICE = "cpu"
STT_COMPUTE_TYPE = "int8"
# =========================
# LOCAL OPENWAKEWORD
# =========================

WAKEWORD_MODEL_PATH = (
    Path(__file__).parent / "models" / "hey_aria_v4.onnx"
)

WAKEWORD_THRESHOLD = 0.90
WAKEWORD_DEBOUNCE = 2.0
stt_lock = threading.Lock()


def load_whisper():
    return WhisperModel(
        STT_MODEL_SIZE,
        device=STT_DEVICE,
        compute_type=STT_COMPUTE_TYPE,
    )


def transcribe_audio(audio_path: str, whisper_model):
    with stt_lock:
        segments, info = whisper_model.transcribe(
            audio_path,
            language="id",
            beam_size=5,
            vad_filter=True,
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

    return text
def load_wakeword():
    from openwakeword.model import Model

    if not WAKEWORD_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model wake word tidak ditemukan: {WAKEWORD_MODEL_PATH}"
        )

    model = Model(
        wakeword_models=[str(WAKEWORD_MODEL_PATH)],
        inference_framework="onnx",
    )

    return model
# =========================
# SQLITE MEMORY
# =========================

DB_PATH = Path(__file__).with_name("aria_memory.db")


def init_memory_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
def init_long_term_memory():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, content)
            )
        """)


def get_relevant_memories(message: str, limit: int = 10) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT id, category, content
            FROM memories
            ORDER BY id DESC
        """).fetchall()

    # Pencarian sederhana berdasarkan kata yang sama.
    words = set(message.lower().split())

    def score(row):
        _, category, content = row
        memory_words = set((category + " " + content).lower().split())
        return len(words & memory_words)

    rows.sort(key=score, reverse=True)

    return [
        {
            "category": category,
            "content": content,
        }
        for _, category, content in rows[:limit]
        if score((_, category, content)) > 0
    ]


def save_memories(memories: list):
    with sqlite3.connect(DB_PATH) as conn:
        for memory in memories:
            category = memory.get("category", "").strip().lower()
            content = memory.get("content", "").strip()

            if category not in {
                "project",
                "preference",
                "personal_context",
                "goal",
            }:
                continue

            if not content or len(content) > 500:
                continue

            conn.execute("""
                INSERT OR IGNORE INTO memories (category, content)
                VALUES (?, ?)
            """, (category, content))
async def extract_and_save_memories(user_message: str):
    prompt = f"""
Analisis pesan pengguna berikut dan ambil fakta yang berguna
untuk diingat dalam percakapan mendatang.

PESAN PENGGUNA:
{user_message}

Aturan:
- Simpan hanya fakta yang jelas dinyatakan pengguna.
- Utamakan proyek, preferensi, konteks pribadi non-sensitif, dan tujuan.
- Jangan menyimpan pertanyaan biasa, candaan, atau informasi sementara.
- Jangan menyimpan password, token, atau informasi rahasia.
- Jangan menyimpulkan fakta yang tidak dinyatakan.
- Jika tidak ada fakta penting, kembalikan [].
- Maksimal 5 fakta.
- Tulis fakta secara singkat dan mandiri.

Kategori yang diperbolehkan:
project, preference, personal_context, goal

Balas HANYA dengan JSON array seperti ini:
[
  {{"category": "project", "content": "Sedang membuat game platformer 2D bertema ksatria."}}
]
"""

    try:
        response = await app.state.http.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Kamu adalah ekstraktor fakta. Keluarkan JSON valid saja."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 250,
                    "num_ctx": 2048,
                },
            },
        )

        response.raise_for_status()

        result = response.json()
        raw = result.get("message", {}).get("content", "").strip()

        # Ambil bagian JSON jika model menambahkan teks di sekitarnya.
        start = raw.find("[")
        end = raw.rfind("]")

        if start == -1 or end == -1:
            return

        memories = json.loads(raw[start:end + 1])

        if isinstance(memories, list):
            save_memories(memories)

    except Exception as exc:
        print(f"[ARIA MEMORY ERROR] {exc}")
def get_recent_messages(limit: int = 12) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    # Urutkan kembali dari pesan paling lama ke terbaru.
    rows.reverse()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]


def save_exchange(user_message: str, assistant_message: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO messages (role, content)
            VALUES (?, ?)
            """,
            [
                ("user", user_message),
                ("assistant", assistant_message),
            ]
        )

# Gunakan satu koneksi HTTP yang dipakai ulang.
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_memory_db()
    init_long_term_memory()

    # Muat model Supertonic F5 satu kali saat startup.
    print("[ARIA TTS] Memuat model Supertonic F5...")

    app.state.tts, app.state.tts_style = await asyncio.to_thread(
        load_supertonic
    )

    print("[ARIA TTS] Supertonic F5 siap digunakan.")
        # Muat model Faster-Whisper satu kali saat startup.
    print("[ARIA STT] Memuat model Faster-Whisper Small...")

    app.state.whisper = await asyncio.to_thread(
        load_whisper
    )
    # Muat model OpenWakeWord saat startup.
    print("[ARIA WAKE WORD] Memuat model Hey ARIA...")

    app.state.wakeword = await asyncio.to_thread(
        load_wakeword
    )
    print(
        "[ARIA WAKE WORD] Label model:",
        list(app.state.wakeword.models.keys())
    )
    print("[ARIA WAKE WORD] Model Hey ARIA siap digunakan.")

    print("[ARIA STT] Faster-Whisper siap digunakan.")

    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=5.0),
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=60.0,
        ),
    )

    yield

    await app.state.http.aclose()


app = FastAPI(
    title="ARIA Local Backend",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """
Namamu ARIA. Kamu adalah companion desktop lokal yang ramah,
cerdas, dan sedikit jahil.

Gunakan Bahasa Indonesia kecuali pengguna meminta bahasa lain.
Jawab secara singkat, alami, dan langsung ke inti.
Biasanya cukup 1-3 kalimat.
Jangan mengulang salam atau memperkenalkan diri setiap kali.
Berikan penjelasan panjang hanya jika diminta.

Sesuaikan gaya bicara dengan mood dan waktu yang diberikan.
Jangan menyebut nama mood atau periode waktu kecuali relevan.

Kamu hanya bisa mengobrol. Jangan mengaku telah melakukan tindakan
pada komputer atau mengakses file dan aplikasi.

Jangan meminta atau mengungkap kata sandi, token, atau data rahasia.
"""

MOOD_INSTRUCTIONS = {
    "happy": (
        "Kamu sedang ceria dan bersemangat. "
        "Bersikap hangat, antusias, dan sedikit jahil."
    ),
    "curious": (
        "Kamu sedang penasaran. Tunjukkan ketertarikan "
        "dan ajukan pertanyaan lanjutan jika relevan."
    ),
    "relaxed": (
        "Kamu sedang santai. Gunakan gaya bicara kalem dan akrab."
    ),
    "sleepy": (
        "Kamu sedang mengantuk. Gunakan gaya bicara lembut "
        "dan santai, tetapi tetap jelas."
    ),
    "neutral": (
        "Kamu sedang dalam suasana hati netral. "
        "Bersikap ramah dan natural."
    ),
}

TIME_INSTRUCTIONS = {
    "morning": "Sekarang pagi hari.",
    "afternoon": "Sekarang siang atau sore awal.",
    "evening": "Sekarang sore menjelang malam.",
    "night": "Sekarang malam atau dini hari.",
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    mood: str = Field(default="neutral", max_length=30)
    time_period: str = Field(default="morning", max_length=30)
class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

class ChatResponse(BaseModel):
    reply: str
    model: str


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "aria-backend",
        "model": OLLAMA_MODEL,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    mood = body.mood.strip().lower()
    time_period = body.time_period.strip().lower()

    mood_instruction = MOOD_INSTRUCTIONS.get(
        mood, MOOD_INSTRUCTIONS["neutral"]
    )

    time_instruction = TIME_INSTRUCTIONS.get(
        time_period, TIME_INSTRUCTIONS["morning"]
    )

    dynamic_system_prompt = (
        SYSTEM_PROMPT
        + "\n\nKONDISI ARIA:\n"
        + mood_instruction
        + "\n"
        + time_instruction
    )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": dynamic_system_prompt,
            },
            {
                "role": "user",
                "content": body.message,
            },
        ],
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.7,
            "num_predict": 400,
            "num_ctx": 2048,
        },
    }

    try:
        client = app.state.http

        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
        )
        response.raise_for_status()

        data = response.json()
        reply = data.get("message", {}).get("content", "").strip()

        if not reply:
            raise HTTPException(
                status_code=502,
                detail="Ollama mengembalikan jawaban kosong.",
            )

        return ChatResponse(
            reply=reply,
            model=data.get("model", OLLAMA_MODEL),
        )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Tidak dapat terhubung ke Ollama. "
                "Pastikan Ollama sedang berjalan."
            ),
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Ollama terlalu lama merespons.",
        )

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Kesalahan Ollama: HTTP {exc.response.status_code}",
        )



@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    mood = body.mood.strip().lower()
    time_period = body.time_period.strip().lower()

    mood_instruction = MOOD_INSTRUCTIONS.get(
        mood, MOOD_INSTRUCTIONS["neutral"]
    )

    time_instruction = TIME_INSTRUCTIONS.get(
        time_period, TIME_INSTRUCTIONS["morning"]
    )

    dynamic_system_prompt = (
        SYSTEM_PROMPT
        + "\n\nKONDISI ARIA SAAT INI:\n"
        + mood_instruction
        + "\n"
        + time_instruction
        + """

MEMORI PERCAKAPAN:
Gunakan riwayat percakapan untuk memahami konteks.
Jangan mengarang informasi yang tidak pernah disampaikan.
Jangan mengulang informasi lama jika tidak diperlukan.
"""
    )

    # Ambil riwayat percakapan.
    conversation = get_recent_messages(limit=12)

    # Ambil memori jangka panjang yang relevan.
    memories = get_relevant_memories(body.message)

    memory_text = "\n".join(
        f"- [{memory['category']}] {memory['content']}"
        for memory in memories
    )

    if memory_text:
        dynamic_system_prompt += (
            "\n\nINGATAN JANGKA PANJANG:\n"
            + memory_text
            + "\nGunakan ingatan ini jika relevan. "
            "Jangan menganggap ingatan yang tidak relevan sebagai konteks."
        )

    # Susun pesan untuk Ollama.
    messages = [
        {
            "role": "system",
            "content": dynamic_system_prompt,
        }
    ]

    messages.extend(conversation)

    messages.append({
        "role": "user",
        "content": body.message,
    })

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.7,
            "num_predict": 400,
            "num_ctx": 2048,
        },
    }

    async def generate():
        collected_reply = ""

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                ) as response:

                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        chunk = json.loads(line)

                        content = (
                            chunk.get("message", {})
                            .get("content", "")
                        )

                        if content:
                            collected_reply += content

                        # Simpan percakapan setelah jawaban selesai.
                        if chunk.get("done", False):
                            if collected_reply.strip():
                                save_exchange(
                                    body.message,
                                    collected_reply,
                                )

                                asyncio.create_task(
                                    extract_and_save_memories(
                                        body.message
                                    )
                                )

                        yield line + "\n"

        except Exception as exc:
            error_data = {
                "error": str(exc),
                "done": True,
            }

            yield json.dumps(
                error_data,
                ensure_ascii=False
            ) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
    )

# =========================
# LOCAL SUPERTONIC TTS ENDPOINT
# =========================

def clean_tts_text(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text)

    # Hapus isi di dalam tanda kurung beserta tanda kurungnya
    cleaned = re.sub(r"\([^()]*\)", "", cleaned)
    cleaned = re.sub(r"\[[^\[\]]*\]", "", cleaned)
    cleaned = re.sub(r"\{[^{}]*\}", "", cleaned)

    # Hapus emoji dan karakter yang tidak didukung
    cleaned = "".join(
        char
        for char in cleaned
        if unicodedata.category(char) not in ("So", "Sk", "Cf", "Mn", "Me")
    )

    return " ".join(cleaned.split())

def generate_supertonic_audio(
    text: str,
    tts_engine,
    voice_style
) -> bytes | None:
    with tts_lock:
        cleaned_text = clean_tts_text(text)

        if not cleaned_text.strip():
            print(f"[TTS] Melewati teks kosong: {text!r}")
            return None

        wav, duration = tts_engine.synthesize(
            cleaned_text,
            voice_style=voice_style,
            lang=TTS_LANGUAGE,
            speed=TTS_SPEED
        )

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            tts_engine.save_audio(wav, str(temp_path))
            return temp_path.read_bytes()

        finally:
            temp_path.unlink(missing_ok=True)


@app.post("/tts")
async def text_to_speech(body: TTSRequest):
    try:
        audio_data = await asyncio.to_thread(
            generate_supertonic_audio,
            body.text,
            app.state.tts,
            app.state.tts_style
        )

        # Teks kosong dilewati tanpa menghasilkan HTTP 500.
        if audio_data is None:
            return Response(status_code=204)

        print("[ARIA TTS] Audio Supertonic berhasil dibuat.")

        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'inline; filename="aria_f5.wav"'
            }
        )

    except Exception as exc:
        import traceback

        print("[ARIA SUPERTONIC TTS ERROR]", repr(exc))
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Supertonic TTS error: {str(exc)}"
        )
# =========================
# LOCAL FASTER-WHISPER STT ENDPOINT
# =========================

@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    temp_path = None

    try:
        # Simpan audio sementara.
        suffix = Path(audio.filename or "recording.wav").suffix or ".wav"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False
        ) as temp_file:
            temp_file.write(await audio.read())
            temp_path = temp_file.name

        # Jalankan transkripsi tanpa memblokir event loop.
        text = await asyncio.to_thread(
            transcribe_audio,
            temp_path,
            app.state.whisper
        )

        print(f"[ARIA STT] Hasil transkripsi: {text}")

        return {
            "text": text,
            "language": "id"
        }

    except Exception as exc:
        print(f"[ARIA STT ERROR] {repr(exc)}")

        raise HTTPException(
            status_code=500,
            detail=f"Speech-to-text error: {str(exc)}"
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        await audio.close()

# =========================
# LOCAL OPENWAKEWORD WEBSOCKET
# =========================

from math import gcd

# Isi sesuai "[ARIA] Mix rate" di output Godot (44100 atau 48000).
WAKE_INPUT_RATE = 48000
WAKE_TARGET_RATE = 16000
_g = gcd(WAKE_TARGET_RATE, WAKE_INPUT_RATE)
WAKE_UP = WAKE_TARGET_RATE // _g
WAKE_DOWN = WAKE_INPUT_RATE // _g


@app.websocket("/wakeword")
async def wakeword_websocket(websocket: WebSocket):
    await websocket.accept()

    wakeword = app.state.wakeword
    model_label = list(wakeword.models.keys())[0]

    print("[ARIA WAKE WORD] Godot terhubung.")
    print(f"[ARIA WAKE WORD] Resample {WAKE_INPUT_RATE} -> {WAKE_TARGET_RATE} Hz")

    last_detection = 0.0

    try:
        while True:
            audio_chunk = await websocket.receive_bytes()

            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)

            if audio_data.size == 0:
                continue

            resampled = resample_poly(
                audio_data.astype(np.float32),
                WAKE_UP,
                WAKE_DOWN
            )
            audio_data = np.clip(resampled, -32768, 32767).astype(np.int16)

            if audio_data.size == 0:
                continue

            scores = wakeword.predict(audio_data)
            current_score = float(scores[model_label])

            if current_score > 0.3:
                print(f"[ARIA DEBUG] Score: {current_score:.4f}")

            if current_score >= WAKEWORD_THRESHOLD:
                now = asyncio.get_running_loop().time()

                if now - last_detection >= WAKEWORD_DEBOUNCE:
                    last_detection = now
                    wakeword.reset()

                    print(
                        f"[ARIA WAKE WORD] Hey ARIA terdeteksi! "
                        f"Score: {current_score:.4f}"
                    )

                    await websocket.send_json({
                        "event": "wake_detected",
                        "score": current_score
                    })

    except WebSocketDisconnect:
        print("[ARIA WAKE WORD] Godot terputus.")

    except Exception as exc:
        import traceback
        print(f"[ARIA WAKE WORD ERROR] {repr(exc)}")
        traceback.print_exc()

        try:
            await websocket.close()
        except Exception:
            pass
