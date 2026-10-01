// The glass card next to the focus object (spec §3). The Overlay moves its group; this component only fills it.

import { t, type I18nKey } from "../i18n";
import { useHud } from "../store";

interface Props {
  onRecheck(trackId: number): void;
}

export default function InfoCard({ onRecheck }: Props) {
  const identity = useHud((s) => {
    const id = s.tracks?.focus_id;
    return id == null ? undefined : s.identities[id];
  });
  const lang = useHud((s) => s.telemetry?.language ?? "de");

  if (!identity) return null;
  return (
    <div className="card glass" aria-live="polite">
      {/* fades in for a new name, not for a new tracker number */}
      <div key={identity.display_name} className="card-body">
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
    </div>
  );
}
