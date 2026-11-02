import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).with_name(".env"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")

app = FastAPI(title="ARIA Local Backend", version="0.1.0")

# Development CORS: local Godot app only. Backend remains bound to loopback.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """
Namamu ARIA. Kamu adalah companion desktop lokal yang ramah, cerdas, dan sedikit jahil.
Jawab dalam Bahasa Indonesia kecuali pengguna meminta bahasa lain.
Jangan mengaku telah melakukan tindakan pada komputer. Pada versi ini kamu hanya chat;
belum ada tool untuk mengakses file, aplikasi, mouse, keyboard, atau perangkat.
Jangan meminta atau mengungkap kata sandi, token, atau data rahasia.
"""

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)

class ChatResponse(BaseModel):
    reply: str
    model: str

@app.get("/health")
async def health():
    return {"ok": True, "service": "aria-backend", "model": OLLAMA_MODEL}

@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": body.message},
        ],
        "stream": False,
        "options": {"temperature": 0.7},
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        reply = data.get("message", {}).get("content", "").strip()
        if not reply:
            raise HTTPException(status_code=502, detail="Ollama mengembalikan jawaban kosong.")
        return ChatResponse(reply=reply, model=data.get("model", OLLAMA_MODEL))
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Tidak dapat terhubung ke Ollama. Pastikan aplikasi Ollama sedang berjalan."
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama terlalu lama merespons.")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Kesalahan Ollama: HTTP {exc.response.status_code}")
