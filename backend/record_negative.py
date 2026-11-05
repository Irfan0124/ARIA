
import os
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000
DURATION = 30
OUTPUT_DIR = "dataset_hey_aria/negative"

os.makedirs(OUTPUT_DIR, exist_ok=True)

existing = [
    f for f in os.listdir(OUTPUT_DIR)
    if f.endswith(".wav")
]
index = len(existing) + 1

input("Tekan Enter untuk merekam suara lingkungan selama 30 detik...")
print("Merekam... Jangan ucapkan Hey ARIA.")

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="int16"
)
sd.wait()

filename = os.path.join(
    OUTPUT_DIR,
    f"negative_{index:03d}.wav"
)

sf.write(filename, audio, SAMPLE_RATE, subtype="PCM_16")
print(f"Berhasil disimpan: {filename}")
