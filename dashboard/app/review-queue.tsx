'use client';

import {
  Asterisk,
  CheckCircle2,
  CircleAlert,
  ShieldCheck,
  Star,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { AuthorizationBadge } from './authorization-badge';
import { jobDescriptionSummary } from './job-description';
import type {
  AuthorizationVerificationFilter,
  Item,
  LocationVerificationFilter,
  Stats,
  Status,
} from './dashboard-types';
import type {
  AuthorizationVerificationCounts,
  LocationVerificationCounts,
} from './review-queue-state';

const labels: Record<Status, string> = {
  new: 'New roles',
  saved: 'Saved',
  rejected: 'Rejected',
  applied: 'Applied',
};
const salary = (job: Item['job']) =>
  !job.salary_min && !job.salary_max
    ? 'Compensation not listed'
    : `\$${job.salary_min ? Math.round(job.salary_min / 1000) : '—'}k – \$${job.salary_max ? Math.round(job.salary_max / 1000) : '—'}k`;
function scoreTone(score: number) {
  if (score < 25) return 'border-red-200 bg-red-50 hover:bg-red-100';
  if (score < 40) return 'border-orange-200 bg-orange-50 hover:bg-orange-100';
  if (score < 60) return 'border-amber-200 bg-amber-50 hover:bg-amber-100';
  if (score < 75)
    return 'border-emerald-100 bg-emerald-50 hover:bg-emerald-100';
  return 'border-green-200 bg-green-100 hover:bg-green-200';
}
function scoreBadge(score: number) {
  if (score < 25) return 'border-red-200 bg-red-100 text-red-800';
  if (score < 40) return 'border-orange-200 bg-orange-100 text-orange-800';
  if (score < 60) return 'border-amber-200 bg-amber-100 text-amber-800';
  return 'border-emerald-200 bg-emerald-100 text-emerald-800';
}

type ReviewQueueProps = {
  status: Status;
  stats: Stats;
  queueLoaded: boolean;
  queueLoading: boolean;
  coverageMinimum: number;
  locationVerification: LocationVerificationFilter;
  locationVerificationCounts: LocationVerificationCounts;
  authorizationVerification: AuthorizationVerificationFilter;
  authorizationVerificationCounts: AuthorizationVerificationCounts;
  visibleItems: Item[];
  selectedKey?: string;
  error: string;
  onStatusChange: (status: Status) => void;
  onCoverageMinimumChange: (minimum: number) => void;
  onLocationVerificationChange: (filter: LocationVerificationFilter) => void;
  onAuthorizationVerificationChange: (
    filter: AuthorizationVerificationFilter,
  ) => void;
  onSelect: (item: Item) => void;
};

export function ReviewQueue({
  status,
  stats,
  queueLoaded,
  queueLoading,
  coverageMinimum,
  locationVerification,
  locationVerificationCounts,
  authorizationVerification,
  authorizationVerificationCounts,
  visibleItems,
  selectedKey,
  error,
  onStatusChange,
  onCoverageMinimumChange,
  onLocationVerificationChange,
  onAuthorizationVerificationChange,
  onSelect,
}: ReviewQueueProps) {
  return (
    <>
      <aside className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-[.14em] text-slate-500">
          Review queue
        </p>
        {(Object.keys(labels) as Status[]).map((key) => (
          <button
            key={key}
            onClick={() => onStatusChange(key)}
            className={`flex w-full justify-between rounded-xl px-3 py-2.5 text-left text-sm ${status === key ? 'bg-indigo-50 font-semibold text-indigo-800' : 'text-slate-600 hover:bg-slate-50'}`}
          >
            <span>{labels[key]}</span>
            <span>{queueLoaded ? (stats.counts[key] ?? 0) : '—'}</span>
          </button>
        ))}
        <div className="mt-4 border-t border-slate-100 px-3 pt-4">
          <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
            Skill coverage
          </p>
          <div className="mt-2 grid gap-1">
            {[0, 50, 75].map((minimum) => (
              <button
                key={minimum}
                onClick={() => onCoverageMinimumChange(minimum)}
                className={`rounded-lg px-2 py-1.5 text-left text-xs ${coverageMinimum === minimum ? 'bg-indigo-50 font-semibold text-indigo-800' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                {minimum ? `${minimum}% or higher` : 'All coverage'}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 border-t border-slate-100 px-3 pt-4">
          <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
            Work location
          </p>
          <div className="mt-2 grid gap-1">
            {(
              [
                ['all', 'All eligible'],
                ['verified', 'Location verified'],
                ['unknown', 'Needs confirmation'],
              ] as [LocationVerificationFilter, string][]
            ).map(([filter, label]) => (
              <button
                key={filter}
                onClick={() => onLocationVerificationChange(filter)}
                aria-pressed={locationVerification === filter}
                className={`flex items-center justify-between rounded-lg px-2 py-1.5 text-left text-xs ${locationVerification === filter ? 'bg-indigo-50 font-semibold text-indigo-800' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                <span>{label}</span>
                <span>
                  {queueLoaded ? locationVerificationCounts[filter] : '—'}
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 border-t border-slate-100 px-3 pt-4">
          <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
            Work authorization
          </p>
          <div className="mt-2 grid gap-1">
            {(
              [
                ['all', 'All authorization'],
                ['verified', 'Authorized'],
                ['sponsorship_required', 'Sponsorship'],
                ['unknown', 'Auth confirm'],
              ] as [AuthorizationVerificationFilter, string][]
            ).map(([filter, label]) => (
              <button
                key={filter}
                onClick={() => onAuthorizationVerificationChange(filter)}
                aria-pressed={authorizationVerification === filter}
                className={`flex items-center justify-between rounded-lg px-2 py-1.5 text-left text-xs ${authorizationVerification === filter ? 'bg-indigo-50 font-semibold text-indigo-800' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                <span>{label}</span>
                <span>
                  {queueLoaded ? authorizationVerificationCounts[filter] : '—'}
                </span>
              </button>
            ))}
          </div>
        </div>
        {queueLoaded && (stats.counts.duplicate ?? 0) > 0 && (
          <p className="px-3 pt-3 text-xs text-slate-500">
            {stats.counts.duplicate} cross-board duplicate
            {stats.counts.duplicate === 1 ? '' : 's'} hidden
          </p>
        )}
        <div className="mt-6 rounded-xl bg-slate-950 p-4 text-xs text-slate-200">
          <ShieldCheck size={16} className="mb-2 text-emerald-300" />
          Your resume, preferences, decisions, and job data stay on this Mac.
        </div>
      </aside>
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex justify-between border-b border-slate-100 px-4 py-3">
          <div>
            <h1 className="font-semibold">{labels[status]}</h1>
            <p className="text-xs text-slate-500">
              Green is strong; red is weak. Select a role for full details.
            </p>
          </div>
          <Badge variant="secondary">
            {queueLoading && !queueLoaded
              ? 'Loading roles…'
              : `${visibleItems.length} shown`}
          </Badge>
        </div>
        {error && (
          <div className="m-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900">
            {error}
          </div>
        )}
        <div className="space-y-1 p-2">
          {visibleItems.map((item) => (
            <button
              key={item.job.key}
              onClick={() => onSelect(item)}
              className={`w-full rounded-lg border px-3 py-2 text-left transition ${scoreTone(item.match.score)} ${selectedKey === item.job.key ? 'ring-2 ring-indigo-400' : ''}`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {item.job.title}
                  </p>
                  <p className="truncate text-xs text-slate-600">
                    {item.job.company} <span className="mx-1">·</span>{' '}
                    {item.job.location || 'Unknown location'}{' '}
                    <span className="mx-1">·</span> {salary(item.job)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Badge
                    variant="outline"
                    className={
                      item.match.country_verification === 'unknown'
                        ? 'border-amber-200 bg-amber-50 text-amber-800'
                        : item.match.country_verification === 'verified'
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                          : 'border-slate-200 bg-slate-50 text-slate-700'
                    }
                    title={
                      item.match.country_verification === 'unknown'
                        ? 'The posting does not confirm eligibility for your configured country or region.'
                        : item.match.country_verification === 'verified'
                          ? 'Work-country or region eligibility is confirmed.'
                          : 'Your profile does not require location verification.'
                    }
                  >
                    {item.match.country_verification === 'unknown'
                      ? 'Location confirm'
                      : item.match.country_verification === 'verified'
                        ? 'Location verified'
                        : 'Location unrestricted'}
                  </Badge>
                  <AuthorizationBadge
                    status={item.match.authorization_verification}
                  />
                  <Badge
                    variant="outline"
                    className={scoreBadge(item.match.score)}
                  >
                    {item.match.score}
                  </Badge>
                </div>
              </div>
              <p className="mt-1 line-clamp-1 text-xs leading-4 text-slate-700">
                {jobDescriptionSummary(item.job.description) ||
                  item.match.reasons
                    .filter((reason) => !reason.startsWith('resume evidence:'))
                    .join(' · ')}
              </p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold text-white">
                <span
                  title={`${item.match.matched_skills.length} skills from your resume match this role`}
                  className="inline-flex items-center gap-1 rounded-full bg-emerald-600/70 px-2.5 py-0.5"
                >
                  <CheckCircle2 size={13} />
                  {item.match.matched_skills.length} matching
                </span>
                <span
                  title={`${item.match.missing_skills.length} role skills are not found in your resume`}
                  className="inline-flex items-center gap-1 rounded-full bg-red-600/70 px-2.5 py-0.5"
                >
                  <CircleAlert size={13} />
                  {item.match.missing_skills.length} missing
                </span>
                <span
                  title={`${item.match.required_role_skills.length} concrete skills are explicitly required by the role`}
                  className="inline-flex items-center gap-1 rounded-full bg-violet-600/70 px-2.5 py-0.5"
                >
                  <Asterisk size={13} />
                  {item.match.required_role_skills.length} required
                </span>
                <span
                  title={`${item.match.matched_preferred_skills.length} preferred skills from your resume match this role`}
                  className="inline-flex items-center gap-1 rounded-full bg-sky-600/70 px-2.5 py-0.5"
                >
                  <Star size={13} />
                  {item.match.matched_preferred_skills.length} preferred
                </span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
