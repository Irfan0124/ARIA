import asyncio
import websockets
import sounddevice as sd
import numpy as np
from scipy.signal import resample_poly

URI = "ws://127.0.0.1:8765/wakeword"

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

async def main():
    print("Menghubungkan ke ARIA...")

    async with websockets.connect(URI) as ws:
        print("Terhubung!")
        print("Ucapkan: Hey ARIA")
        print("Tekan CTRL+C untuk berhenti.")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SIZE
        ) as stream:

            while True:
                audio, overflowed = stream.read(CHUNK_SIZE)

                if overflowed:
                    print("Audio overflow!")

                await ws.send(audio.tobytes())

                try:
                    message = await asyncio.wait_for(
                        ws.recv(),
                        timeout=0.01
                    )
                    print("ARIA:", message)

                except asyncio.TimeoutError:
                    pass

asyncio.run(main())