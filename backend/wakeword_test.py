
import time
import numpy as np
import pyaudiowpatch as pyaudio
from openwakeword.model import Model

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280

print("[ARIA] Memuat model...")
model = Model(
    wakeword_models=["hey_jarvis"],
    inference_framework="onnx"
)

audio = pyaudio.PyAudio()

try:
    device = audio.get_default_input_device_info()
    print("[ARIA] Mikrofon:", device["name"])

    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=int(device["index"]),
        frames_per_buffer=CHUNK_SIZE
    )

    print("[ARIA] Tes mikrofon dimulai.")
    print("[ARIA] Ucapkan Hey Jarvis.")
    print("[ARIA] Ctrl+C untuk berhenti.\n")

    last_status = time.time()
    last_detection = 0
    latest_score = 0.0
    latest_rms = 0.0

    while True:
        data = stream.read(
            CHUNK_SIZE,
            exception_on_overflow=False
        )

        samples = np.frombuffer(data, dtype=np.int16)

        latest_rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

        prediction = model.predict(samples)
        latest_score = float(prediction.get("hey_jarvis", 0.0))

        if latest_score >= 0.5 and time.time() - last_detection > 2:
            print(f"\n[ARIA] WAKE WORD TERDETEKSI! Skor: {latest_score:.3f}")
            last_detection = time.time()

        if time.time() - last_status >= 1:
            print(
                f"[MIC] RMS: {latest_rms:.1f} | "
                f"Skor Hey Jarvis: {latest_score:.4f}"
            )
            last_status = time.time()

except KeyboardInterrupt:
    print("\n[ARIA] Pengujian dihentikan.")

finally:
    if "stream" in locals():
        stream.stop_stream()
        stream.close()

    audio.terminate()
