import sounddevice as sd
import numpy as np
from openwakeword.model import Model

model = Model(
    wakeword_models=["models/hey_aria.onnx"],
    inference_framework="onnx"
)

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280

print("Mikrofon aktif. Ucapkan: HEY ARIA")
print("Tekan Ctrl+C untuk berhenti.\n")

try:
    with sd.InputStream(
    device=1,
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="int16",
    blocksize=CHUNK_SIZE
    ) as stream:
        while True:
            audio, overflowed = stream.read(CHUNK_SIZE)
            audio = np.squeeze(audio)

            prediction = model.predict(audio)
            score = prediction["hey_aria"]

            print(f"Skor Hey ARIA: {score:.4f}", end="\r")

            if score >= 0.3:
                print(f"\nKANDIDAT DETEKSI! Skor: {score:.4f}")

except KeyboardInterrupt:
    print("\nTes dihentikan.")