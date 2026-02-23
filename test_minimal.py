import asyncio, os, sys
sys.stdout.reconfigure(line_buffering=True)
from google import genai
from google.genai import types

print("1. Creating client...", flush=True)
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY", ""),
    http_options={"api_version": "v1beta"},
)

MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
        )
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
)

print("2. Connecting...", flush=True)

async def main():
    try:
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as s:
            print("3. CONNECTED!", flush=True)
            await s.send(input="Say hi", end_of_turn=True)
            async for r in s.receive():
                if r.data:
                    print(f"4. Audio: {len(r.data)}b", flush=True)
                if r.server_content and r.server_content.turn_complete:
                    print("5. Done", flush=True)
                    break
    except Exception as e:
        print(f"FAIL: {e}", flush=True)

asyncio.run(main())
print("6. Finished", flush=True)
