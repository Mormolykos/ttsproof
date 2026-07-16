# SpeechSDK Integration

This example demonstrates how to benchmark closed-source models (like OpenAI, ElevenLabs, Google, etc.) using [SpeechSDK](https://speechsdk.dev/). SpeechSDK provides a unified API for over 17 TTS providers.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Set your environment variables. You must specify the model using `SPEECHSDK_MODEL`, and provide the API key for the respective provider (e.g., `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`).
   ```bash
   export SPEECHSDK_MODEL="openai/gpt-4o-mini-tts"
   export SPEECHSDK_VOICE="alloy"
   export OPENAI_API_KEY="sk-..."
   ```
   *Note: most providers require `SPEECHSDK_VOICE` — without it the SDK returns
   `"voice" is required when routing through the speech gateway in inline mode`.
   Use a voice id valid for your chosen provider (e.g. `alloy` for OpenAI).*

## Benchmarking

Run the `ttsproof` benchmark utilizing the wrapper script:

```bash
ttsproof benchmark --cmd "node examples/speechsdk/speak.mjs {text} {out}"
```

> [!WARNING]  
> **Cost Warning:** Running the full 817-case corpus against a paid API costs real money. 

To run a smaller subset for testing, you can use the `--limit` flag:

```bash
ttsproof benchmark --limit 10 --cmd "node examples/speechsdk/speak.mjs {text} {out}"
```
