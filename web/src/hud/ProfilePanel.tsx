// The product profile next to the info card (sub-project 2): Claude's own knowledge, no sources, always marked as such.

import { t } from "../i18n";
import { focusProfile, useHud } from "../store";

export default function ProfilePanel() {
  const profile = useHud(focusProfile);
  const lang = useHud((s) => s.telemetry?.language ?? "de");
  if (!profile) return null;
  const note = { loading: "profile.loading", unknown: "profile.unknown", error: "profile.error", ready: null } as const;
  const noteKey = note[profile.status];

  return (
    <aside className="profile glass" aria-live="polite">
      <div className="profile-head">
        <span className="card-level">{t("profile.title", lang)}</span>
        <span className="tag">{t("profile.byClaude", lang)}</span>
      </div>
      {noteKey && <p className="profile-note">{t(noteKey, lang)}</p>}
      {profile.status === "ready" && (
        <div key={profile.product} className="card-body">
          <p className="profile-summary">{profile.summary}</p>
          {profile.facts.length > 0 && (
            <dl className="facts">
              {profile.facts.map((fact, i) => (
                <div key={`${i}-${fact.label}`}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>
              ))}
            </dl>
          )}
          {(profile.released || profile.launch_price) && (
            <p className="profile-meta">
              {profile.released && <span><b>{t("profile.released", lang)}</b> {profile.released}</span>}
              {profile.launch_price && <span><b>{t("profile.price", lang)}</b> {profile.launch_price}</span>}
            </p>
          )}
          {profile.trivia.length > 0 && (
            <>
              <div className="card-level">{t("profile.trivia", lang)}</div>
              <ul className="trivia">{profile.trivia.map((x) => <li key={x}>{x}</li>)}</ul>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
