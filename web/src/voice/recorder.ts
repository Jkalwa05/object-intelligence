// Push-to-talk (sub-project 4): the microphone is open only while the space bar is held. The samples are brought to
// 16 kHz mono and sent as 16-bit PCM; Whisper on the Mac turns them into text.

export const RATE = 16000;
export const MIN_SECONDS = 0.3; // shorter is a tap, not a question
export const MAX_SECONDS = 30;

// Linear resampling; enough for speech.
export function downsample(samples: Float32Array, fromRate: number): Float32Array {
  if (fromRate === RATE) return samples;
  const count = Math.round((samples.length * RATE) / fromRate);
  const out = new Float32Array(count);
  const step = (samples.length - 1) / Math.max(1, count - 1);
  for (let i = 0; i < count; i++) {
    const position = i * step;
    const low = Math.floor(position);
    const high = Math.min(samples.length - 1, low + 1);
    out[i] = samples[low] + (samples[high] - samples[low]) * (position - low);
  }
  return out;
}

export function toPcmBase64(samples: Float32Array): string {
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) pcm[i] = Math.round(Math.max(-1, Math.min(1, samples[i])) * 32767);
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

// Copies every block of the microphone signal to the main thread.
const TAP = `class Tap extends AudioWorkletProcessor {
  process(inputs) { const channel = inputs[0] && inputs[0][0]; if (channel) this.port.postMessage(channel.slice(0)); return true; }
}
registerProcessor("tap", Tap);`;

export interface Recording {
  stop(): Promise<{ samples: Float32Array; seconds: number }>;
}

export async function record(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const context = new AudioContext();
  const url = URL.createObjectURL(new Blob([TAP], { type: "application/javascript" }));
  await context.audioWorklet.addModule(url);
  URL.revokeObjectURL(url);
  const source = context.createMediaStreamSource(stream);
  const tap = new AudioWorkletNode(context, "tap");
  const silent = context.createGain();
  silent.gain.value = 0; // the tap must be part of a running graph, but nothing should be heard
  const chunks: Float32Array[] = [];
  tap.port.onmessage = (event) => chunks.push(event.data as Float32Array);
  source.connect(tap).connect(silent).connect(context.destination);
  return {
    async stop() {
      source.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      const rate = context.sampleRate;
      await context.close();
      const all = new Float32Array(chunks.reduce((n, chunk) => n + chunk.length, 0));
      let offset = 0;
      for (const chunk of chunks) {
        all.set(chunk, offset);
        offset += chunk.length;
      }
      return { samples: downsample(all, rate), seconds: all.length / rate };
    },
  };
}
