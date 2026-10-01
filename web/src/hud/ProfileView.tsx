// The product profile (sub-project 2) inside a sidebar entry: Claude's own knowledge, no sources, marked as such.

import { t } from "../i18n";
import type { Lang, ProfileMsg } from "../protocol";

const NOTE = { loading: "profile.loading", unknown: "profile.unknown", error: "profile.error", ready: null } as const;

export default function ProfileView({ profile, lang }: { profile: ProfileMsg; lang: Lang }) {
  const note = NOTE[profile.status];
  return (
    <div className="entry-part" aria-live="polite">
      <div className="profile-head">
        <span className="card-level">{t("profile.title", lang)}</span>
        <span className="tag">{t("profile.byClaude", lang)}</span>
      </div>
      {note && <p className="profile-note">{t(note, lang)}</p>}
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
    </div>
  );
}
