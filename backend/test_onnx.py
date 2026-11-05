import numpy as np
import soundfile as sf
import onnxruntime as ort
from openwakeword.utils import AudioFeatures

audio, sr = sf.read(
    r"C:\Users\Hype AMD\Documents\aria\backend\models\test_hey_aria.wav",
    dtype="int16"
)

features = AudioFeatures(inference_framework="onnx")

session = ort.InferenceSession(
    r"C:\Users\Hype AMD\Documents\aria\backend\models\hey_aria_v4.onnx",
    providers=["CPUExecutionProvider"]
)

scores = []

for i in range(0, len(audio) - 32000 + 1, 8000):
    clip = audio[i:i + 32000]
    embedding = features.embed_clips(clip.reshape(1, -1)).astype(np.float32)
    score = session.run(None, {"x": embedding})[0][0][0]
    scores.append((i / sr, float(score)))

for t, score in scores:
    print(f"{t:.2f}s : {score:.4f}", "DETECTED" if score >= 0.5 else "")

print("Skor tertinggi:", round(max(s for _, s in scores), 4))