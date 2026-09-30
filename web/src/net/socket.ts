import { isServerMsg, type ServerMsg } from "../protocol";

export const RECONNECT_MS = 2000;
export const REPLACED_CODE = 4000; // the server closed us because another tab connected

export type ConnectionStatus = "open" | "closed" | "replaced";

export interface Connection {
  send(data: ArrayBuffer | string): void;
  bufferedAmount(): number;
  close(): void;
}

export function connect(
  url: string,
  handlers: { onMessage(message: ServerMsg): void; onStatus(status: ConnectionStatus): void },
): Connection {
  let ws: WebSocket | null = null;
  let stopped = false;
  let timer: number | undefined;

  const open = () => {
    ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => handlers.onStatus("open");
    ws.onmessage = (event) => {
      if (typeof event.data !== "string") return;
      try {
        const message: unknown = JSON.parse(event.data);
        if (isServerMsg(message)) handlers.onMessage(message);
      } catch {
        // ignore anything that is not valid JSON
      }
    };
    ws.onclose = (event) => {
      if (event.code === REPLACED_CODE) {
        handlers.onStatus("replaced"); // two tabs must not keep replacing each other
        return;
      }
      handlers.onStatus("closed");
      if (!stopped) timer = window.setTimeout(open, RECONNECT_MS);
    };
  };
  open();

  return {
    send: (data) => {
      if (ws?.readyState === WebSocket.OPEN) ws.send(data);
    },
    bufferedAmount: () => (ws?.readyState === WebSocket.OPEN ? ws.bufferedAmount : Number.POSITIVE_INFINITY),
    close: () => {
      stopped = true;
      window.clearTimeout(timer);
      ws?.close();
    },
  };
}
