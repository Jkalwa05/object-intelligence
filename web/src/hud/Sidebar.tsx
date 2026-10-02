// The sidebar on the right (sub-projects 3 and 6): every identified object stays pinned as an entry. The object in
// the hand is expanded on top; the others are collapsed and open with a click, like a drop-down.

import { lazy, Suspense, useMemo } from "react";
import { useShallow } from "zustand/react/shallow";
import { t, type I18nKey } from "../i18n";
import { entriesFor, fullscreenView, useHud, type SidebarEntry } from "../store";
import IdentityView from "./IdentityView";
import ProfileView from "./ProfileView";
import QuestionsView from "./QuestionsView";

const Hologram = lazy(() => import("./Hologram")); // three.js loads only once a model is shown
const HologramFullscreen = lazy(() => import("./HologramFullscreen"));

interface Actions {
  onRecheck(trackId: number): void;
  onConfirm(trackId: number, name: string): void;
  onRebuild(name: string): void;
  onKeep(model: string, kept: boolean): void;
}

// The hologram in full screen stays open on its own: putting the object down folds its entry up, not this view.
function Fullscreen({ onKeep }: Pick<Actions, "onKeep">) {
  const view = useHud(useShallow(fullscreenView));
  const lang = useHud((s) => s.telemetry?.language ?? "de");
  const close = useHud((s) => s.setFullscreen);
  if (!view) return null;
  return (
    <Suspense fallback={null}>
      <HologramFullscreen model={view.model} identity={view.identity} profile={view.profile} lang={lang}
        onClose={() => close(null)} onKeep={onKeep} />
    </Suspense>
  );
}

function Entry({ entry, onRecheck, onConfirm, onRebuild }: { entry: SidebarEntry } & Omit<Actions, "onKeep">) {
  const lang = useHud((s) => s.telemetry?.language ?? "de");
  const profile = useHud((s) => s.profiles[entry.name]);
  const model = useHud((s) => s.models[entry.name]);
  const toggle = useHud((s) => s.toggleEntry);
  const { identity } = entry;
  const known = identity.level === "likely" || identity.level === "certain"; // the profile needs this
  const named = identity.level !== null && identity.level !== "category_only"; // a product: a model may come
  const state = identity.status === "analysing" ? t("analysing", lang)
    : identity.level ? t(`level.${identity.level}` as I18nKey, lang) : "";

  return (
    <section className={entry.active ? "entry glass active" : "entry glass"}>
      <button type="button" className="entry-head" aria-expanded={entry.expanded} onClick={() => toggle(entry.name)}>
        <span className="entry-name">{entry.name}</span>
        <span className="entry-state" data-level={identity.level ?? "none"} data-status={identity.status}>{state}</span>
        <span className="entry-chevron" aria-hidden="true">{entry.expanded ? "▾" : "▸"}</span>
      </button>
      {entry.expanded && (
        <div className="entry-body">
          <IdentityView identity={identity} lang={lang} onRecheck={entry.active ? onRecheck : undefined}
            onConfirm={onConfirm} />
          <QuestionsView name={entry.name} lang={lang} />
          {named && (
            <Suspense fallback={null}>
              <Hologram name={entry.name} level={identity.level} model={model} lang={lang} onRebuild={onRebuild} />
            </Suspense>
          )}
          {known && profile && <ProfileView profile={profile} lang={lang} />}
        </div>
      )}
    </section>
  );
}

export default function Sidebar({ onRecheck, onConfirm, onRebuild, onKeep }: Actions) {
  const lang = useHud((s) => s.telemetry?.language ?? "de");
  const focusId = useHud((s) => s.tracks?.focus_id ?? null); // tracks change every frame, the focus rarely
  const slice = useHud(useShallow((s) => ({ identities: s.identities, named: s.named, recent: s.recent, open: s.open })));
  const entries = useMemo(() => entriesFor(slice, focusId), [slice, focusId]);

  return (
    <aside className="sidebar">
      <div className="sidebar-title card-level">{t("sidebar.title", lang)}</div>
      {entries.map((entry) => (
        <Entry key={entry.name} entry={entry} onRecheck={onRecheck} onConfirm={onConfirm} onRebuild={onRebuild} />
      ))}
      <Fullscreen onKeep={onKeep} />
    </aside>
  );
}
