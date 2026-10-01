// The identification of one object (spec §3), inside its sidebar entry: name, line, candidates, evidence, the view
// that would decide, and "Neu prüfen" for the object in the hand.

import { t } from "../i18n";
import type { IdentityMsg, Lang } from "../protocol";

interface Props {
  identity: IdentityMsg;
  lang: Lang;
  onRecheck?: (trackId: number) => void; // only for the object in the hand
}

export default function IdentityView({ identity, lang, onRecheck }: Props) {
  return (
    // fades in for a new name, not for a new tracker number
    <div key={identity.display_name} className="card-body">
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
      {onRecheck && (
        <button type="button" className="pill" onClick={() => onRecheck(identity.track_id)}>{t("recheck", lang)}</button>
      )}
    </div>
  );
}
