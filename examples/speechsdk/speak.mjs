import fs from 'node:fs';
import { generateSpeech } from '@speech-sdk/core';

async function main() {
  const [, , text, outPath] = process.argv;
  if (!text || !outPath) {
    console.error('Usage: node speak.mjs "<text>" <output_path>');
    process.exit(1);
  }

  const model = process.env.SPEECHSDK_MODEL;
  if (!model) {
    console.error('Error: SPEECHSDK_MODEL environment variable is required (e.g., openai/gpt-4o-mini-tts)');
    process.exit(1);
  }

  try {
    const result = await generateSpeech({
      model: model,
      text: text,
      voice: process.env.SPEECHSDK_VOICE || undefined,
    });
    
    fs.writeFileSync(outPath, result.audio.uint8Array);
  } catch (err) {
    console.error('SpeechSDK error:', err.message);
    process.exit(1);
  }
}

main();
