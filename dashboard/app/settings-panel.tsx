'use client';

import { ChangeEvent, useCallback, useEffect, useState } from 'react';
import { FileText, FileUp, Save } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { ApplicationTracker } from './application-tracker';
import type {
  Config,
  Decision,
  Learning,
  Profile,
  Stats,
} from './dashboard-types';

const API = '';
const listFields: Array<
  keyof Pick<
    Profile,
    | 'locations'
    | 'employment_types'
    | 'title_priorities'
    | 'eligible_countries'
    | 'work_authorized_countries'
    | 'excluded_terms'
  >
> = [
  'locations',
  'employment_types',
  'title_priorities',
  'eligible_countries',
  'work_authorized_countries',
  'excluded_terms',
];
const list = (value: string) =>
  value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
const dateTime = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(value))
    : 'Not yet fetched';

export function SettingsPanel({
  config,
  stats,
  decisions,
  profileJson,
  setProfileJson,
  message,
  busy,
  onSave,
  onUpload,
}: {
  config: Config | null;
  stats: Stats;
  decisions: Decision[];
  profileJson: string;
  setProfileJson: (value: string) => void;
  message: string;
  busy: boolean;
  onSave: (profile: Profile, message: string) => Promise<void>;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
}) {
  const [draftOverride, setDraftOverride] = useState<Profile | null>(null);
  const [resumeReview, setResumeReview] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const draft = draftOverride ?? config?.profile ?? null;
  if (!config || !draft)
    return (
      <div className="mx-auto max-w-5xl p-10 text-sm text-slate-500">
        Loading configuration…
      </div>
    );
  const update = (key: keyof Profile, value: unknown) =>
    setDraftOverride({ ...draft, [key]: value });
  const save = async (profile: Profile, confirmation: string) => {
    setDraftOverride(profile);
    await onSave(profile, confirmation);
  };
  const valid = (() => {
    try {
      JSON.parse(profileJson);
      return true;
    } catch {
      return false;
    }
  })();
  const healthy = stats.sources.filter((source) => !source.error).length;
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-5 py-6 lg:px-10">
      <div className="flex justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-indigo-700">
            Private configuration
          </p>
          <h1 className="text-2xl font-semibold">Tune the job search</h1>
        </div>
        <Badge
          variant={
            healthy === stats.sources.length ? 'secondary' : 'destructive'
          }
        >
          {healthy}/{stats.sources.length} sources healthy
        </Badge>
      </div>
      {message && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-950">
          {message}
        </div>
      )}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">Update your resume and profile</h2>
        <p className="mt-1 text-sm text-slate-500">
          DOCX is the preferred source for format-preserving tailored resumes.
          PDF remains available for matching and review.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold">
            1
          </span>
          <label
            htmlFor="resume-docx-upload"
            className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white"
          >
            <FileUp size={16} /> Upload DOCX (preferred)
            <Input
              id="resume-docx-upload"
              className="hidden"
              type="file"
              accept="application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx"
              disabled={busy}
              onChange={(event) => void onUpload(event)}
            />
          </label>
          <label
            htmlFor="resume-pdf-upload"
            className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800"
          >
            <FileUp size={16} /> Upload PDF
            <Input
              id="resume-pdf-upload"
              className="hidden"
              type="file"
              accept="application/pdf,.pdf"
              disabled={busy}
              onChange={(event) => void onUpload(event)}
            />
          </label>
          {config.resume.present && (
            <span className="text-xs text-slate-500">
              Active source: {config.resume.name} (
              {config.resume.source_format?.toUpperCase()})
            </span>
          )}
        </div>
        {config.resume.pdf_present && config.resume.docx_present && (
          <p className="mt-3 text-xs text-indigo-700">
            Both sources are saved privately. The DOCX is selected for
            tailoring; the PDF remains preserved.
          </p>
        )}
        {config.resume_draft && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm">
            <div className="flex items-center gap-2 font-medium text-emerald-900">
              <FileText size={16} /> Resume changes are ready
            </div>
            <p className="mt-1 text-emerald-800">
              The draft can update skills, evidence, and profile details. It is
              not committed until you approve it.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setProfileJson(JSON.stringify(config.profile, null, 2));
                  setResumeReview(false);
                  setAdvancedOpen(false);
                }}
              >
                View current profile
              </Button>
              <Button
                onClick={() => {
                  setProfileJson(JSON.stringify(config.resume_draft, null, 2));
                  setResumeReview(true);
                  setAdvancedOpen(true);
                }}
              >
                2. Review resume changes
              </Button>
              <Button
                disabled={!resumeReview || !valid || busy}
                onClick={() =>
                  void save(
                    JSON.parse(profileJson) as Profile,
                    'Resume-derived profile changes committed locally.',
                  )
                }
              >
                <Save /> 3. Commit approved changes
              </Button>
            </div>
            {resumeReview && (
              <p className="mt-3 text-xs font-medium text-emerald-900">
                Review the Advanced profile JSON below, then commit only when it
                is accurate.
              </p>
            )}
            {config.resume_text_preview && (
              <details className="mt-3 text-emerald-950">
                <summary className="cursor-pointer">
                  View full extracted resume text
                </summary>
                <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs">
                  {config.resume_text_preview}
                </pre>
              </details>
            )}
          </div>
        )}
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex justify-between">
          <div>
            <h2 className="font-semibold">Matching preferences</h2>
            <p className="text-sm text-slate-500">
              Target geography and work authorization are evaluated separately.
              Save, reject, and apply decisions to improve ranking.
            </p>
          </div>
          <Button
            disabled={busy}
            onClick={() =>
              void save(draft, 'Matching preferences saved locally.')
            }
          >
            <Save /> Save changes
          </Button>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Field
            label="Minimum salary"
            type="number"
            value={draft.minimum_salary ?? ''}
            onChange={(value) =>
              update('minimum_salary', value ? Number(value) : null)
            }
          />
          <Field
            label="Maximum travel (%)"
            type="number"
            value={draft.max_travel_percentage ?? ''}
            onChange={(value) =>
              update('max_travel_percentage', value ? Number(value) : null)
            }
          />
          {listFields.map((field) => (
            <Field
              key={field}
              label={
                field === 'locations'
                  ? 'Local locations (also accepts remote roles)'
                  : field === 'eligible_countries'
                    ? 'Target job countries or regions'
                    : field === 'work_authorized_countries'
                      ? 'Work-authorized countries'
                      : field.replaceAll('_', ' ')
              }
              value={(draft[field] ?? []).join(', ')}
              onChange={(value) => update(field, list(value))}
            />
          ))}
          <div className="flex items-center justify-between rounded-xl border p-3">
            <div>
              <span className="text-sm font-medium">Include remote roles</span>
              <p className="text-xs text-slate-500">
                Target countries and regions still control geographic scope.
              </p>
            </div>
            <Switch
              aria-label="Include remote roles"
              checked={draft.remote_ok}
              onCheckedChange={(checked) => update('remote_ok', checked)}
            />
          </div>
          <div className="flex items-center justify-between rounded-xl border p-3">
            <div>
              <span className="text-sm font-medium">
                Consider roles requiring sponsorship
              </span>
              <p className="text-xs text-slate-500">
                Outside your authorized countries, keep roles unless the posting
                explicitly says sponsorship is unavailable.
              </p>
            </div>
            <Switch
              aria-label="Consider roles requiring sponsorship"
              checked={draft.consider_sponsorship_roles}
              onCheckedChange={(checked) =>
                update('consider_sponsorship_roles', checked)
              }
            />
          </div>
        </div>
      </section>
      <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <summary className="cursor-pointer font-semibold">
          Custom skill aliases{' '}
          <span className="ml-2 text-sm font-normal text-slate-500">
            Optional equivalent terminology
          </span>
        </summary>
        <div className="mt-4">
          <AliasEditor
            key={JSON.stringify(draft.skill_aliases ?? {})}
            profile={draft}
            busy={busy}
            onSave={save}
          />
        </div>
      </details>
      <details
        open={advancedOpen}
        onToggle={(event) =>
          setAdvancedOpen((event.target as HTMLDetailsElement).open)
        }
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <summary className="cursor-pointer font-semibold">
          Advanced profile JSON{' '}
          <span className="ml-2 text-sm font-normal text-slate-500">
            Developer controls and full resume-derived data
          </span>
        </summary>
        <div className="mt-4">
          <div className="flex justify-end">
            <Button
              variant="outline"
              disabled={!valid || busy}
              onClick={() =>
                void save(
                  JSON.parse(profileJson) as Profile,
                  'Advanced profile JSON saved locally.',
                )
              }
            >
              <Save /> Save JSON
            </Button>
          </div>
          <Textarea
            className="mt-4 min-h-[360px] font-mono text-xs"
            value={profileJson}
            onChange={(event) => setProfileJson(event.target.value)}
            spellCheck={false}
          />
          {!valid && (
            <p className="mt-2 text-sm text-red-600">
              Fix the JSON before saving.
            </p>
          )}
        </div>
      </details>
      <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <summary className="cursor-pointer font-semibold">
          Decision history{' '}
          <span className="ml-2 text-sm font-normal text-slate-500">
            {stats.learning?.positive_decision_terms ?? 0} positive and{' '}
            {stats.learning?.negative_decision_terms ?? 0} negative learning
            signals
          </span>
        </summary>
        {decisions.length ? (
          <div className="mt-4 space-y-2">
            {decisions.slice(0, 10).map((decision) => (
              <div
                key={`${decision.job_key}-${decision.decided_at}`}
                className="rounded-xl border border-slate-100 p-3 text-sm"
              >
                <div className="flex justify-between gap-3">
                  <span className="font-medium">
                    {decision.title || decision.job_key}
                  </span>
                  <Badge
                    variant={
                      decision.status === 'rejected'
                        ? 'destructive'
                        : decision.status === 'applied'
                          ? 'default'
                          : 'secondary'
                    }
                  >
                    {decision.status}
                  </Badge>
                </div>
                <p className="text-xs text-slate-500">
                  {decision.company ? `${decision.company} · ` : ''}
                  {dateTime(decision.decided_at)}
                </p>
                {decision.note && (
                  <p className="mt-1 text-slate-700">{decision.note}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            No decisions yet. Your first reviews will appear here and begin
            shaping future ranking.
          </p>
        )}
      </details>
      <ApplicationTracker />
      <LearningAudit />
    </div>
  );
}
function Field({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label>
      <span className="text-sm font-medium capitalize">{label}</span>
      <Input
        className="mt-2"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Comma-separated values"
      />
    </label>
  );
}

function AliasEditor({
  profile,
  busy,
  onSave,
}: {
  profile: Profile;
  busy: boolean;
  onSave: (profile: Profile, message: string) => Promise<void>;
}) {
  const [value, setValue] = useState(() =>
    JSON.stringify(profile.skill_aliases ?? {}, null, 2),
  );
  const aliases = (() => {
    try {
      const parsed = JSON.parse(value);
      return parsed &&
        typeof parsed === 'object' &&
        !Array.isArray(parsed) &&
        Object.values(parsed).every(
          (terms) =>
            Array.isArray(terms) &&
            terms.every((term) => typeof term === 'string'),
        )
        ? (parsed as Record<string, string[]>)
        : null;
    } catch {
      return null;
    }
  })();
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Custom skill aliases</h2>
          <p className="mt-1 text-sm text-slate-500">
            Map a profile skill to equivalent wording used in job descriptions,
            such as AWS to Amazon Web Services.
          </p>
        </div>
        <Button
          disabled={!aliases || busy}
          onClick={() =>
            aliases &&
            void onSave(
              { ...profile, skill_aliases: aliases },
              'Skill aliases saved locally.',
            )
          }
        >
          <Save /> Save aliases
        </Button>
      </div>
      <Textarea
        className="mt-4 min-h-40 font-mono text-xs"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        spellCheck={false}
        placeholder={'{\n  "AWS": ["Amazon Web Services"]\n}'}
      />
      {!aliases && (
        <p className="mt-2 text-sm text-red-600">
          Use a JSON object whose values are lists of alternate terms.
        </p>
      )}
    </section>
  );
}

function LearningAudit() {
  const [learning, setLearning] = useState<Learning | null>(null);
  const load = useCallback(async () => {
    const response = await fetch(`${API}/api/learning`);
    if (response.ok) setLearning((await response.json()) as Learning);
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const ignore = async (term: string, ignored: boolean) => {
    await fetch(`${API}/api/learning/ignore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term, ignored }),
    });
    await load();
  };
  if (!learning) return null;
  const terms = [
    ...learning.terms.positive.map((item) => ({ ...item, kind: 'positive' })),
    ...learning.terms.negative.map((item) => ({ ...item, kind: 'negative' })),
  ];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold">Learning audit</h2>
      <p className="mt-1 text-sm text-slate-500">
        Ignore any title/company term that is skewing recommendations. This
        never deletes your decision history.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {terms.map((item) => (
          <button
            key={`${item.kind}-${item.term}`}
            onClick={() => void ignore(item.term, true)}
            className={`rounded-full border px-3 py-1 text-sm ${item.kind === 'positive' ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-red-200 bg-red-50 text-red-900'}`}
          >
            {item.kind === 'positive' ? '+' : '−'} {item.term} ({item.count})
          </button>
        ))}
      </div>
      {learning.ignored.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
            Ignored terms
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {learning.ignored.map((term) => (
              <button
                key={term}
                onClick={() => void ignore(term, false)}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-sm text-slate-700"
              >
                Restore {term}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
