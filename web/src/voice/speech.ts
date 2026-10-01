// When does the voice speak (spec §3)? Only for the focus object and only new lines. It is off until M is pressed.

import type { Lang } from "../protocol";

// macOS joke voices, as learned in Kalwa (Dead-EV3/kalwa/ui/static/js/speech.js).
export const NOVELTY_VOICES = new Set(["Albert", "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Wobble",
  "Fred", "Good News", "Jester", "Junior", "Kathy", "Organ", "Ralph", "Superstar", "Trinoids", "Whisper", "Zarvox"]);

const baseName = (name: string) => name.split(" (")[0];

export function pickVoice<V extends { name: string; lang: string }>(voices: V[], lang: Lang): V | null {
  return voices.find((v) => v.lang.toLowerCase().startsWith(lang) && !NOVELTY_VOICES.has(baseName(v.name))) ?? null;
}

export interface SpeechEvent {
  trackId: number;
  line: string;
}

export class SpeechGate {
  private spoken = new Map<number, Set<string>>();

  reset(): void {
    this.spoken.clear();
  }

  // The tracker gave the same object a new number: what was said about it stays said.
  carry(from: number, to: number): void {
    this.spoken.set(to, new Set([...(this.spoken.get(to) ?? []), ...(this.spoken.get(from) ?? [])]));
  }

  // Returns the line to speak now, or null.
  consider(event: SpeechEvent, focusId: number | null, muted: boolean): string | null {
    if (muted || !event.line || event.trackId !== focusId) return null;
    const lines = this.spoken.get(event.trackId) ?? new Set<string>();
    if (lines.has(event.line)) return null;
    lines.add(event.line);
    this.spoken.set(event.trackId, lines);
    return event.line;
  }
}
