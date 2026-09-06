import type { SkillContext } from './dashboard-types';

export { roleSkillCoverage } from './review-queue-state';
export function SkillGroup({
  label,
  skills = [],
  headingClassName,
  pillClassName,
  empty,
  onSkillClick,
}: {
  label: string;
  skills?: string[];
  headingClassName: string;
  pillClassName: string;
  empty: string;
  onSkillClick?: (skill: string) => void;
}) {
  return (
    <div>
      <p
        className={`text-xs font-semibold uppercase tracking-[.12em] ${headingClassName}`}
      >
        {label}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {skills.length ? (
          skills.map((skill) =>
            onSkillClick ? (
              <button
                key={skill}
                type="button"
                title={`Add ${skill} to your profile`}
                onClick={() => onSkillClick(skill)}
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium transition hover:brightness-95 ${pillClassName}`}
              >
                {skill} +
              </button>
            ) : (
              <span
                key={skill}
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${pillClassName}`}
              >
                {skill}
              </span>
            ),
          )
        ) : (
          <span className="text-sm text-slate-500">{empty}</span>
        )}
      </div>
    </div>
  );
}
export function SkillEvidence({
  contexts = [],
}: {
  contexts?: SkillContext[];
}) {
  const tone = {
    high: 'border-violet-200 bg-violet-50 text-violet-800',
    medium: 'border-amber-200 bg-amber-50 text-amber-800',
    low: 'border-slate-200 bg-slate-50 text-slate-700',
  };
  return (
    <section className="mt-5 rounded-xl border border-slate-200 p-3">
      <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
        Description evidence
      </p>
      <p className="mt-1 text-xs text-slate-500">
        Confidence reflects how directly the skill is stated: explicit
        requirement, strong capability language, or incidental mention.
      </p>
      <div className="mt-3 space-y-2">
        {contexts.map((entry) => (
          <div key={entry.skill} className="rounded-lg bg-slate-50 p-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-800">
                {entry.skill}
              </span>
              <span
                className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold capitalize ${tone[entry.confidence]}`}
              >
                {entry.confidence}
              </span>
            </div>
            <p className="mt-1 text-xs leading-4 text-slate-600">
              {entry.context}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
