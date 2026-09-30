import { encodeFrame } from "./frame";

const MAX_WIDTH = 1280;
const JPEG_QUALITY = 0.8;

export function openCamera(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
    audio: false,
  });
}

// Sends at most `fps` JPEG frames per second, never mirrored, and only while the socket is not backed up.
// Returns a function that stops the loop.
export function startCapture(
  video: HTMLVideoElement,
  send: (buffer: ArrayBuffer) => void,
  canSend: () => boolean,
  fps = 12,
): () => void {
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  let frameId = 0;
  let busy = false;
  const timer = window.setInterval(() => {
    if (!context || busy || !canSend() || video.readyState < 2 || !video.videoWidth) return;
    const scale = Math.min(1, MAX_WIDTH / video.videoWidth);
    const w = Math.round(video.videoWidth * scale);
    const h = Math.round(video.videoHeight * scale);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    context.drawImage(video, 0, 0, w, h);
    const t = performance.now();
    busy = true;
    canvas.toBlob(async (blob) => {
      busy = false;
      if (blob) send(encodeFrame({ frame_id: ++frameId, t_capture_ms: t, w, h }, await blob.arrayBuffer()));
    }, "image/jpeg", JPEG_QUALITY);
  }, 1000 / fps);
  return () => window.clearInterval(timer);
}
