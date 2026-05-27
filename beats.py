"""
Chocojam beat backend.

Captures system audio via WASAPI loopback, detects kick-drum onsets
in the bass band using spectral flux, and broadcasts beat events
over a WebSocket so the browser overlay can headbop the goat in sync.
"""

import asyncio
import json
import threading
import time
from collections import deque

import numpy as np
import pyaudiowpatch as pyaudio
import websockets


# ── Tunables ──────────────────────────────────────────────────────────────
CHUNK              = 1024     # samples per audio frame
BASS_LOW_HZ        = 40       # kick drum band
BASS_HIGH_HZ       = 180
HISTORY_SECONDS    = 1.2      # rolling window for the adaptive threshold
BEAT_THRESHOLD     = 1.4      # bass_flux must exceed median * this
BEAT_MIN_INTERVAL  = 0.16     # min seconds between beats (~375 BPM cap)
WARMUP_FRAMES      = 15       # ignore beats while history fills

WS_HOST = "127.0.0.1"
WS_PORT = 7321
# ──────────────────────────────────────────────────────────────────────────


clients: set[websockets.WebSocketServerProtocol] = set()
loop: asyncio.AbstractEventLoop | None = None


def broadcast(message: str):
    """Thread-safe broadcast from the audio thread into the asyncio loop."""
    if loop is None or not clients:
        return
    asyncio.run_coroutine_threadsafe(_broadcast(message), loop)


async def _broadcast(message: str):
    if not clients:
        return
    await asyncio.gather(
        *(c.send(message) for c in list(clients)),
        return_exceptions=True,
    )


async def handle_client(ws):
    clients.add(ws)
    print(f"  + overlay connected ({len(clients)} total)")
    try:
        await ws.wait_closed()
    finally:
        clients.discard(ws)
        print(f"  - overlay disconnected ({len(clients)} left)")


def audio_loop():
    p = pyaudio.PyAudio()
    try:
        device = p.get_default_wasapi_loopback()
    except OSError:
        print("ERROR: no WASAPI loopback device. Make sure audio is enabled.")
        return

    print(f"Listening on: {device['name']}")
    print()

    rate     = int(device["defaultSampleRate"])
    channels = device["maxInputChannels"]

    stream = p.open(
        format=pyaudio.paFloat32,
        channels=channels,
        rate=rate,
        input=True,
        frames_per_buffer=CHUNK,
        input_device_index=device["index"],
    )

    freqs     = np.fft.rfftfreq(CHUNK, d=1.0 / rate)
    bass_mask = (freqs >= BASS_LOW_HZ) & (freqs <= BASS_HIGH_HZ)

    prev_spectrum = np.zeros(len(freqs), dtype=np.float32)
    flux_history  = deque(maxlen=int(HISTORY_SECONDS * rate / CHUNK))
    last_beat     = 0.0
    frame_idx     = 0

    try:
        while True:
            data    = stream.read(CHUNK, exception_on_overflow=False)
            samples = np.frombuffer(data, dtype=np.float32)
            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1)

            spectrum = np.abs(np.fft.rfft(samples)).astype(np.float32)

            # Spectral flux: how much louder is each bin compared to the
            # previous frame? Only positive changes (rising energy) — this
            # is the textbook onset detector for kick drums.
            diff      = np.maximum(spectrum - prev_spectrum, 0)
            bass_flux = float(diff[bass_mask].sum())
            prev_spectrum = spectrum

            flux_history.append(bass_flux)
            frame_idx += 1
            if frame_idx < WARMUP_FRAMES:
                continue

            # Median is more robust than mean against transient spikes
            threshold = float(np.median(flux_history)) * BEAT_THRESHOLD

            now = time.time()
            if (
                bass_flux > threshold
                and bass_flux > 0.5  # absolute floor — kills false fires on near-silence
                and (now - last_beat) > BEAT_MIN_INTERVAL
            ):
                last_beat = now
                intensity = min(1.0, bass_flux / max(threshold * 2, 1.0))
                broadcast(json.dumps({"type": "beat", "intensity": intensity}))
                print(f"  beat  flux={bass_flux:6.2f}  thr={threshold:6.2f}  i={intensity:.2f}")
    finally:
        stream.close()
        p.terminate()


async def main():
    global loop
    loop = asyncio.get_running_loop()

    thread = threading.Thread(target=audio_loop, daemon=True)
    thread.start()

    async with websockets.serve(handle_client, WS_HOST, WS_PORT):
        print(f"WebSocket: ws://{WS_HOST}:{WS_PORT}")
        print("Add overlay.html as a Browser Source in Streamlabs.")
        print("Ctrl+C to stop.")
        print()
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
