import { useEffect, useRef, useState } from "react";
import { openCamera, startCapture } from "./camera/capture";
import Banner from "./hud/Banner";
import InfoCard from "./hud/InfoCard";
import Overlay from "./hud/Overlay";
import Telemetry from "./hud/Telemetry";
import { connect, type Connection } from "./net/socket";
import type { Lang, RecalibrateMsg, RecheckMsg } from "./protocol";
import { useHud } from "./store";
import { SpeechGate, pickVoice } from "./voice/speech";
import "./styles.css";

const MAX_BUFFERED_BYTES = 1_000_000;

function say(line: string | null, lang: Lang) {
  if (!line || !("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(line);
  const voice = pickVoice(window.speechSynthesis.getVoices(), lang);
  if (voice) utterance.voice = voice;
  utterance.lang = lang === "de" ? "de-DE" : "en-US";
  window.speechSynthesis.speak(utterance);
}

// The voice follows the store: new lines of the focus object, hints at most every 5 s (spec §3).
function useVoice() {
  useEffect(() => {
    const gate = new SpeechGate();
    let focus: number | null = null;
    return useHud.subscribe((s, prev) => {
      const synth = "speechSynthesis" in window ? window.speechSynthesis : null;
      const focusId = s.tracks?.focus_id ?? null;
      const lang: Lang = s.telemetry?.language ?? "de";
      const now = performance.now();
      if (s.connection === "open" && prev.connection !== "open") gate.reset(); // fresh pipeline, IDs start at 1
      if (focusId !== focus || (s.muted && !prev.muted)) synth?.cancel();
      focus = focusId;
      if (focusId === null) return;
      const identity = s.identities[focusId];
      if (identity && identity !== prev.identities[focusId]) {
        say(gate.consider({ trackId: focusId, line: identity.line, kind: "result" }, now, focusId, s.muted), lang);
      }
      if (s.tracks !== prev.tracks && s.tracks?.hint) {
        say(gate.consider({ trackId: focusId, line: s.tracks.hint, kind: "hint" }, now, focusId, s.muted), lang);
      }
    });
  }, []);
}

export default function App() {
  const video = useRef<HTMLVideoElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const connection = useRef<Connection | null>(null);
  const mirrored = useHud((s) => s.mirrored);
  const [cameraAttempt, setCameraAttempt] = useState(0);

  useEffect(() => {
    const { receive, setConnection } = useHud.getState();
    const c = connect(`ws://${location.host}/ws`, { onMessage: receive, onStatus: setConnection });
    connection.current = c;
    return () => c.close();
  }, []);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let stopCapture = () => {};
    let cancelled = false;
    useHud.getState().setCameraError(null);
    openCamera()
      .then((s) => {
        stream = s;
        if (cancelled || !video.current) return;
        video.current.srcObject = s;
        stopCapture = startCapture(video.current, (b) => connection.current?.send(b),
          () => (connection.current?.bufferedAmount() ?? Number.POSITIVE_INFINITY) < MAX_BUFFERED_BYTES);
      })
      .catch((error: unknown) => useHud.getState().setCameraError(String(error)));
    return () => {
      cancelled = true;
      stopCapture();
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [cameraAttempt]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const s = useHud.getState();
      if (event.key === "m") s.toggleMute();
      else if (event.key === "d") s.toggleTelemetry();
      else if (event.key === "s") s.toggleMirror();
      else if (event.key === "r") connection.current?.send(JSON.stringify({ type: "recalibrate" } satisfies RecalibrateMsg));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useVoice();

  const send = (message: RecheckMsg) => connection.current?.send(JSON.stringify(message));

  return (
    <main className="stage">
      <video ref={video} className={mirrored ? "video mirrored" : "video"} autoPlay playsInline muted />
      <Overlay video={video} card={card} />
      <InfoCard cardRef={card} onRecheck={(trackId) => send({ type: "recheck", track_id: trackId })} />
      <Telemetry video={video} />
      <Banner onRetryCamera={() => setCameraAttempt((n) => n + 1)} />
    </main>
  );
}
