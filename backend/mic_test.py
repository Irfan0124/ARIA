import sounddevice as sd
import numpy as np

def callback(indata, frames, time, status):
    audio = indata[:, 0]
    volume = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
    print(f"Volume: {volume:.0f}")

with sd.InputStream(
    device=1,
    samplerate=16000,
    channels=1,
    dtype="int16",
    blocksize=1280,
    callback=callback
):
    print("Bicara ke mikrofon selama 10 detik...")
    sd.sleep(10000)

print("Tes selesai.")