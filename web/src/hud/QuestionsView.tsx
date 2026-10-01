// Spoken questions about one object and Claude's answers (sub-project 4), oldest first, inside its sidebar entry.

import { t, type I18nKey } from "../i18n";
import { questionsFor, useHud } from "../store";
import type { Lang } from "../protocol";

export default function QuestionsView({ name, lang }: { name: string; lang: Lang }) {
  const questions = useHud((s) => questionsFor(s, name));
  if (questions.length === 0) return null;
  return (
    <div className="entry-part" aria-live="polite">
      <div className="card-level">{t("questions", lang)}</div>
      {questions.map((q) => (
        <div key={q.qid} className="qa">
          {q.question && <p className="qa-question">„{q.question}“</p>}
          {q.status === "ready" || q.status === "error" ? (
            <p className="qa-answer">{q.answer}</p>
          ) : (
            <p className="profile-note">{t(`q.${q.status}` as I18nKey, lang)}</p>
          )}
          {q.sources.length > 0 && (
            <p className="qa-sources">
              {q.sources.map((source) => (
                <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
              ))}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
