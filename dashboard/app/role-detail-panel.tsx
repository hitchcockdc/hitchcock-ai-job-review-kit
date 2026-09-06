'use client';

import {
  Bookmark,
  ExternalLink,
  Send,
  Sparkles,
  ThumbsDown,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { AuthorizationBadge } from './authorization-badge';
import { cleanJobDescription, jobDescriptionSummary } from './job-description';
import { roleSkillCoverage, SkillEvidence, SkillGroup } from './role-skills';
import { TailorResume } from './tailor-resume';
import type { Item, Status } from './dashboard-types';

function scoreBadge(score: number) {
  if (score < 25) return 'border-red-200 bg-red-100 text-red-800';
  if (score < 40) return 'border-orange-200 bg-orange-100 text-orange-800';
  if (score < 60) return 'border-amber-200 bg-amber-100 text-amber-800';
  return 'border-emerald-200 bg-emerald-100 text-emerald-800';
}
function reasonTone(reason: string) {
  if (reason.startsWith('matched required skills:')) return 'text-violet-700';
  if (reason.startsWith('matched skills:')) return 'text-emerald-700';
  if (reason.startsWith('role skills not yet in resume:'))
    return 'text-red-700';
  return 'text-slate-800';
}

type RoleDetailPanelProps = {
  selected: Item | null;
  reasons: string[];
  note: string;
  busy: boolean;
  onNoteChange: (note: string) => void;
  onReview: (status: Exclude<Status, 'new'>) => void;
  onMissingSkillClick: (skill: string) => void;
};

export function RoleDetailPanel({
  selected,
  reasons,
  note,
  busy,
  onNoteChange,
  onReview,
  onMissingSkillClick,
}: RoleDetailPanelProps) {
  return (
    <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:sticky lg:top-6 lg:h-[calc(100vh-48px)] lg:overflow-y-auto">
      {selected ? (
        <>
          <div className="flex flex-wrap gap-2">
            <Badge
              variant="outline"
              className={scoreBadge(selected.match.score)}
            >
              {selected.match.score}/100 match
            </Badge>
            <AuthorizationBadge
              status={selected.match.authorization_verification}
            />
          </div>
          <h2 className="mt-3 text-lg font-semibold">{selected.job.title}</h2>
          <p className="text-sm text-slate-500">
            {selected.job.company} · {selected.job.location}
          </p>
          <a
            href={selected.job.url}
            target="_blank"
            rel="noreferrer"
            className="mt-5 inline-flex w-full justify-center gap-2 rounded-lg bg-slate-950 px-3 py-2 text-sm font-medium text-white"
          >
            Open employer application <ExternalLink size={15} />
          </a>
          <section className="mt-6 rounded-xl bg-slate-50 p-3 text-sm">
            <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
              Role summary
            </p>
            <p className="mt-2 leading-5 text-slate-700">
              {jobDescriptionSummary(selected.job.description) ||
                'No description was provided by the employer.'}
            </p>
          </section>
          <details className="mt-4 rounded-xl border border-slate-200 p-3 text-sm">
            <summary className="cursor-pointer font-medium text-slate-800">
              Full job description
            </summary>
            <p className="mt-3 whitespace-pre-wrap leading-6 text-slate-700">
              {cleanJobDescription(selected.job.description) ||
                'No description was provided by the employer.'}
            </p>
          </details>
          <section className="mt-6">
            <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
              Why this fits
            </p>
            <ul className="mt-3 space-y-2 text-sm">
              {reasons.map((reason, index) => (
                <li key={`${reason}-${index}`} className={reasonTone(reason)}>
                  • {reason}
                </li>
              ))}
            </ul>
          </section>
          <section className="mt-5 rounded-xl border border-slate-200 p-3">
            <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
              Role skills
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Click a red skill to add it to your local profile. Amber items
              were found in the detailed description outside an explicit
              requirements section.
            </p>
            <div className="mt-4 space-y-4">
              <SkillGroup
                label={`Your matching skills (${roleSkillCoverage(selected.match)}%)`}
                skills={selected.match.matched_skills}
                headingClassName="text-emerald-700"
                pillClassName="border-emerald-200 bg-emerald-50 text-emerald-700"
                empty="No resume skills detected."
              />
              <SkillGroup
                label="Missing from resume"
                skills={selected.match.missing_skills}
                headingClassName="text-red-700"
                pillClassName="border-red-200 bg-red-50 text-red-700"
                empty="No concrete gaps detected."
                onSkillClick={onMissingSkillClick}
              />
              <SkillGroup
                label="Required by role"
                skills={selected.match.required_role_skills}
                headingClassName="text-violet-700"
                pillClassName="border-violet-200 bg-violet-50 text-violet-700"
                empty="No required skills detected."
              />
              <SkillGroup
                label="Buried in detailed description"
                skills={selected.match.buried_role_skills}
                headingClassName="text-amber-700"
                pillClassName="border-amber-200 bg-amber-50 text-amber-800"
                empty="No additional concrete capabilities detected."
              />
              <SkillGroup
                label="Preferred skills you match"
                skills={selected.match.matched_preferred_skills}
                headingClassName="text-sky-700"
                pillClassName="border-sky-200 bg-sky-50 text-sky-700"
                empty="No preferred skills detected."
              />
            </div>
          </section>
          <SkillEvidence contexts={selected.match.role_skill_contexts} />
          {selected.match.evidence[0] && (
            <section className="mt-5 rounded-xl bg-indigo-50 p-3 text-sm">
              <p className="text-xs font-semibold text-indigo-700">
                Resume evidence
              </p>
              <p className="mt-1">{selected.match.evidence[0]}</p>
            </section>
          )}
          <TailorResume key={selected.job.key} job={selected.job} />
          <label
            htmlFor="decision-note"
            className="mt-5 block text-xs font-semibold uppercase tracking-[.12em] text-slate-500"
          >
            Decision note
            <Textarea
              id="decision-note"
              value={note}
              onChange={(event) => onNoteChange(event.target.value)}
              className="mt-2"
              placeholder="Why this role is or isn't worth pursuing…"
            />
          </label>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => onReview('saved')}
            >
              <Bookmark /> Save
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() => onReview('rejected')}
            >
              <ThumbsDown /> Reject
            </Button>
            <Button disabled={busy} onClick={() => onReview('applied')}>
              <Send /> Applied
            </Button>
          </div>
        </>
      ) : (
        <div className="grid h-full place-items-center text-center text-sm text-slate-500">
          <div>
            <Sparkles className="mx-auto mb-3 text-indigo-500" />
            Select a role to review.
          </div>
        </div>
      )}
    </aside>
  );
}
