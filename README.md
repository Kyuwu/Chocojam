# Chocojam

Choco headbops to the beat of whatever's playing on your system audio. Drop the overlay into a transparent browser source for a live reactive stream overlay.

## Preview

https://lightless.media/u/hUkluCcR.mp4

---

## How it works

- `beats.py` captures system audio via WASAPI loopback (works with Spotify, YouTube, anything that plays through your default output)
- Detects kick drums by tracking energy in the 40–150 Hz bass band against a rolling average
- Broadcasts beat events over a local WebSocket (`ws://127.0.0.1:7321`)
- `overlay.html` connects, scales + tilts the choco on each beat, transparent background ready for OBS/Streamlabs

---

## Setup (one time)

1. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

2. In **Streamlabs** → your scene → **Add Source** → **Browser Source**:
   - **URL** (Local file checkbox ON): `path\to\yo\overlay.html`
   - **Width** / **Height**: whatever fits your scene (e.g. 600 × 600)
   - **Custom CSS**: leave default (transparent body is set in the HTML)
   - **Shutdown source when not visible**: ✗ (so it stays connected)
   - Click Done.

---

## Each stream

1. Double-click `start.bat` (or run `python beats.py`)
2. Play music. Choco bops.

Leave the terminal window open while streaming — closing it stops the beat detection. Minimize it, don't close it.

---

## Tuning

If the choco bops too often / not enough, open `beats.py` and tweak:

| Setting | Effect |
|---|---|
| `BEAT_THRESHOLD` | Higher = pickier (fewer beats). Default `1.55` |
| `BEAT_MIN_INTERVAL` | Min seconds between beats. Default `0.18` |
| `BASS_LOW_HZ` / `BASS_HIGH_HZ` | Frequency band. Default 40–150 Hz (kick drums) |

The console prints `beat  intensity=X.XX` per detected beat, so you can see what's firing while you tune.

---

## Troubleshooting

- **Overlay shows "offline — start beats.py"** → `beats.py` isn't running, or it crashed. Check the terminal.
- **No beats detected** → make sure audio is actually playing through your **default output device**. WASAPI loopback only captures what the default device plays.
- **Choco bops on speech/silence** → lower `BEAT_THRESHOLD` or narrow the bass band.
- **pyaudiowpatch install fails** → make sure you're on Windows (it's Windows-only) and using a recent Python.
