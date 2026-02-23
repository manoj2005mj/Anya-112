"""Quick test: can we connect to Gemini Live API?"""
import asyncio, sys
sys.stdout.reconfigure(line_buffering=True)

from app.services.gemini import client, MODEL, LIVE_CONNECT_CONFIG

print(f"MODEL = {MODEL}")
# Show which config fields are set
for k, v in LIVE_CONNECT_CONFIG.__dict__.items():
    if v is not None:
        print(f"  config.{k} = {type(v).__name__}")

async def main():
    print("\nConnecting to Gemini Live...")
    try:
        async with client.aio.live.connect(model=MODEL, config=LIVE_CONNECT_CONFIG) as session:
            print("✅ CONNECTED")
            await session.send(input="Say hello in one sentence", end_of_turn=True)
            print("Waiting for response...")
            async for r in session.receive():
                if r.data:
                    print(f"  🔊 audio chunk: {len(r.data)} bytes")
                if r.text:
                    print(f"  💬 text: {r.text[:100]}")
                sc = r.server_content
                if sc:
                    if sc.output_transcription and sc.output_transcription.text:
                        print(f"  📝 transcript: {sc.output_transcription.text}")
                    if sc.turn_complete:
                        print("  ✅ turn complete")
                        break
            print("\nSUCCESS")
    except Exception as e:
        print(f"\n❌ FAILED: {type(e).__name__}: {e}")

asyncio.run(main())
