// The glass card next to the focus object (spec §3). The Overlay moves it; this component only fills it.

import type { RefObject } from "react";
import { t, type I18nKey } from "../i18n";
import { useHud } from "../store";

interface Props {
  cardRef: RefObject<HTMLDivElement | null>;
  onRecheck(trackId: number): void;
}

export default function InfoCard({ cardRef, onRecheck }: Props) {
  const identity = useHud((s) => {
    const id = s.tracks?.focus_id;
    return id == null ? undefined : s.identities[id];
  });
  const lang = useHud((s) => s.telemetry?.language ?? "de");

  return (
    <div ref={cardRef} className={identity ? "card glass" : "card glass hidden"} aria-live="polite">
      {identity && (
        <div key={identity.track_id} className="card-body">
          <div className="card-level">
            {identity.status === "analysing" ? t("analysing", lang)
              : identity.level ? t(`level.${identity.level}` as I18nKey, lang) : ""}
          </div>
          <div className="card-name">{identity.display_name}</div>
          {identity.line && <div className="card-line">{identity.line}</div>}
          {identity.candidates.length > 0 && (
            <ul className="bars">
              {identity.candidates.map((c) => (
                <li key={c.name}><span>{c.name}</span><i style={{ width: `${Math.round(c.share * 100)}%` }} /></li>
              ))}
            </ul>
          )}
          {identity.evidence.length > 0 && (
            <div className="chips">
              {identity.evidence.map((e, i) => (
                <span key={e} className="chip" style={{ animationDelay: `${i * 80}ms` }}>{e}</span>
              ))}
            </div>
          )}
          {identity.view_request && (
            <div className="ask">
              ↓ {t("showMe", lang)} {identity.view_request.view}
              <small>{identity.view_request.reason}</small>
            </div>
          )}
          <button type="button" className="pill" onClick={() => onRecheck(identity.track_id)}>{t("recheck", lang)}</button>
        </div>
      )}
    </div>
  );
}
