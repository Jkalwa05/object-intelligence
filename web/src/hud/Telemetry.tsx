// Top-left numbers (key D): the only place in the HUD where confidence shares appear as numbers (spec §3).

import { useEffect, useState, type RefObject } from "react";
import { t, type I18nKey } from "../i18n";
import { useHud } from "../store";

export default function Telemetry({ video }: { video: RefObject<HTMLVideoElement | null> }) {
  const show = useHud((s) => s.showTelemetry);
  const muted = useHud((s) => s.muted);
  const tel = useHud((s) => s.telemetry);
  const shares = useHud((s) => {
    const id = s.tracks?.focus_id;
    return id == null ? undefined : s.identities[id]?.candidates;
  });
  const [videoFps, setVideoFps] = useState(0);

  useEffect(() => {
    const v = video.current;
    if (!v || !("requestVideoFrameCallback" in v)) return;
    let frames = 0, since = performance.now(), handle = 0;
    const tick = () => {
      frames += 1;
      const now = performance.now();
      if (now - since >= 1000) {
        setVideoFps(Math.round((frames * 1000) / (now - since)));
        frames = 0;
        since = now;
      }
      handle = v.requestVideoFrameCallback(tick);
    };
    handle = v.requestVideoFrameCallback(tick);
    return () => v.cancelVideoFrameCallback(handle);
  }, [video]);

  const lang = tel?.language ?? "de";
  const badge = muted ? null : <div className="muted-badge glass">{t("voiceOn", lang)}</div>;
  if (!show) return badge;
  const rows: [string, string][] = [
    [t("tel.fpsVideo", lang), `${videoFps} fps`],
    [t("tel.fpsProcessed", lang), tel ? `${tel.fps_processed.toFixed(1)} fps` : "–"],
    [t("tel.detMs", lang), tel ? `${tel.det_ms.toFixed(0)} ms` : "–"],
    [t("tel.idLast", lang), tel?.id_ms_last != null ? `${(tel.id_ms_last / 1000).toFixed(1)} s` : "–"],
    [t("tel.sharpness", lang), tel?.sharpness_focus != null ? tel.sharpness_focus.toFixed(0) : "–"],
    [t("tel.gate", lang), tel ? t(`gate.${tel.gate_focus ?? "ok"}` as I18nKey, lang) : "–"],
    [t("tel.calls", lang), tel ? String(tel.calls_session) : "–"],
    [t("tel.cost", lang), tel ? `$${tel.cost_session_usd.toFixed(3)}` : "–"],
    [t("tel.model", lang), tel?.model ?? "–"],
    [t("tel.mode", lang), tel?.mode ?? "–"],
    [t("tel.dropped", lang), tel ? String(tel.frames_dropped) : "–"],
  ];
  if (shares?.length) rows.push([t("tel.shares", lang), shares.map((c) => `${c.name} ${c.share.toFixed(2)}`).join(" · ")]);

  return (
    <>
      <dl className="telemetry glass">
        {rows.map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
        ))}
      </dl>
      {badge}
    </>
  );
}
