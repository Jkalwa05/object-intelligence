// The sidebar on the right (sub-project 3): every identified object stays pinned as an entry. The object in the hand
// is expanded on top; the others are collapsed and open with a click, like a drop-down.

import { lazy, Suspense, useMemo } from "react";
import { useShallow } from "zustand/react/shallow";
import { t, type I18nKey } from "../i18n";
import { entriesFor, useHud, type SidebarEntry } from "../store";
import IdentityView from "./IdentityView";
import ProfileView from "./ProfileView";

const Hologram = lazy(() => import("./Hologram")); // three.js loads only once a hologram is shown

function Entry({ entry, onRecheck }: { entry: SidebarEntry; onRecheck(trackId: number): void }) {
  const lang = useHud((s) => s.telemetry?.language ?? "de");
  const profile = useHud((s) => s.profiles[entry.name]);
  const shape = useHud((s) => s.shapes[entry.name]);
  const toggle = useHud((s) => s.toggleEntry);
  const { identity } = entry;
  const known = identity.level === "likely" || identity.level === "certain"; // profile and hologram need this
  const state = identity.status === "analysing" ? t("analysing", lang)
    : identity.level ? t(`level.${identity.level}` as I18nKey, lang) : "";

  return (
    <section className={entry.active ? "entry glass active" : "entry glass"}>
      <button type="button" className="entry-head" aria-expanded={entry.expanded} onClick={() => toggle(entry.name)}>
        <span className="entry-name">{entry.name}</span>
        <span className="entry-state">{state}</span>
        <span className="entry-chevron" aria-hidden="true">{entry.expanded ? "▾" : "▸"}</span>
      </button>
      {entry.expanded && (
        <div className="entry-body">
          <IdentityView identity={identity} lang={lang} onRecheck={entry.active ? onRecheck : undefined} />
          {known && profile && <ProfileView profile={profile} lang={lang} />}
          {known && shape && <Suspense fallback={null}><Hologram shape={shape} lang={lang} /></Suspense>}
        </div>
      )}
    </section>
  );
}

export default function Sidebar({ onRecheck }: { onRecheck(trackId: number): void }) {
  const lang = useHud((s) => s.telemetry?.language ?? "de");
  const focusId = useHud((s) => s.tracks?.focus_id ?? null); // tracks change every frame, the focus rarely
  const slice = useHud(useShallow((s) => ({ identities: s.identities, named: s.named, recent: s.recent, open: s.open })));
  const entries = useMemo(() => entriesFor(slice, focusId), [slice, focusId]);

  return (
    <aside className="sidebar">
      <div className="sidebar-title card-level">{t("sidebar.title", lang)}</div>
      {entries.map((entry) => <Entry key={entry.name} entry={entry} onRecheck={onRecheck} />)}
    </aside>
  );
}
