// Glass banners at the top centre: camera problems, connection state and the server's notices (spec §3, §4).

import { useEffect, useState } from "react";
import { t } from "../i18n";
import { focusHint, useHud } from "../store";

const INFO_VISIBLE_MS = 6000;

export default function Banner({ onRetryCamera }: { onRetryCamera(): void }) {
  const notices = useHud((s) => s.notices);
  const connection = useHud((s) => s.connection);
  const cameraError = useHud((s) => s.cameraError);
  const hint = useHud(focusHint);
  const lang = useHud((s) => s.telemetry?.language ?? "de");
  const latest = notices.at(-1);
  const [expiredSeq, setExpiredSeq] = useState<number | null>(null);

  useEffect(() => {
    if (!latest || latest.level !== "info") return;
    const timer = window.setTimeout(() => setExpiredSeq(latest.seq), INFO_VISIBLE_MS);
    return () => window.clearTimeout(timer);
  }, [latest]);

  const items = [];
  if (cameraError) {
    items.push(
      <div key="camera" className="banner glass">
        {t("cameraDenied", lang)} <button type="button" className="pill" onClick={onRetryCamera}>{t("retry", lang)}</button>
      </div>,
    );
  }
  if (connection === "replaced") items.push(<div key="replaced" className="banner glass">{t("replaced", lang)}</div>);
  else if (connection === "closed") items.push(<div key="closed" className="banner glass">{t("reconnecting", lang)}</div>);
  if (hint) items.push(<div key="hint" className="banner glass">{hint}</div>);
  if (latest && latest.seq !== expiredSeq) {
    items.push(<div key={`notice-${latest.seq}`} className="banner glass">{latest.text}</div>);
  }
  return items.length ? <div className="banner-stack">{items}</div> : null;
}
