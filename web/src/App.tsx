import { useEffect, useRef, useState } from "react";
import { openCamera, startCapture } from "./camera/capture";
import { connect, type ConnectionStatus } from "./net/socket";

// Task 10 shell: camera video and connection state. The HUD is added on top in Task 12.
export default function App() {
  const video = useRef<HTMLVideoElement>(null);
  const [status, setStatus] = useState<ConnectionStatus>("closed");

  useEffect(() => {
    const connection = connect(`ws://${location.host}/ws`, { onMessage: () => {}, onStatus: setStatus });
    let stopCapture = () => {};
    let stream: MediaStream | null = null;
    openCamera().then((s) => {
      stream = s;
      if (!video.current) return;
      video.current.srcObject = s;
      stopCapture = startCapture(video.current, connection.send, () => connection.bufferedAmount() < 1_000_000);
    });
    return () => {
      stopCapture();
      stream?.getTracks().forEach((t) => t.stop());
      connection.close();
    };
  }, []);

  return (
    <main style={{ position: "fixed", inset: 0, background: "#000" }}>
      <video ref={video} autoPlay playsInline muted
        style={{ width: "100%", height: "100%", objectFit: "contain", transform: "scaleX(-1)" }} />
      <span style={{ position: "absolute", left: 12, top: 12, color: "#fff", font: "12px -apple-system" }}>{status}</span>
    </main>
  );
}
