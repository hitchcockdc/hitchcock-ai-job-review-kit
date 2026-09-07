'use client';

import { useState } from 'react';
import { Eye, RotateCcw, Save } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type {
  Profile,
  ScoringPreview,
  ScoringWeightKey,
  ScoringWeights,
} from './dashboard-types';
import {
  DEFAULT_SCORING_WEIGHTS,
  SCORING_COMPONENTS,
  SYNTHETIC_SCORE_EXAMPLES,
  scoringDirectionTotal,
  scoringWeightTotal,
  scoringWeights,
  syntheticScore,
} from './scoring';

export function ScoreWeightSettings({
  profile,
  busy,
  onSave,
}: {
  profile: Profile;
  busy: boolean;
  onSave: (profile: Profile, message: string) => Promise<void>;
}) {
  const current = scoringWeights(profile.scoring_weights);
  const [draft, setDraft] = useState<ScoringWeights>(current);
  const [queuePreview, setQueuePreview] = useState<ScoringPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const total = scoringWeightTotal(draft);
  const changed = SCORING_COMPONENTS.some(
    ({ key }) => draft[key] !== current[key],
  );
  const draftIsDefault = SCORING_COMPONENTS.every(
    ({ key }) => draft[key] === DEFAULT_SCORING_WEIGHTS[key],
  );
  const update = (key: ScoringWeightKey, value: string) => {
    const parsed = Number(value);
    setQueuePreview(null);
    setPreviewError('');
    setDraft((weights) => ({
      ...weights,
      [key]: Number.isInteger(parsed) ? Math.min(100, Math.max(0, parsed)) : 0,
    }));
  };
  const previewQueue = async () => {
    setPreviewBusy(true);
    setPreviewError('');
    try {
      const response = await fetch('/api/scoring-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weights: draft, limit: 10 }),
      });
      const payload = (await response.json()) as ScoringPreview & {
        error?: string;
      };
      if (!response.ok)
        throw new Error(
          payload.error || 'Could not preview the current queue.',
        );
      setQueuePreview(payload);
    } catch (cause) {
      setPreviewError(
        cause instanceof Error
          ? cause.message
          : 'Could not preview the current queue.',
      );
    } finally {
      setPreviewBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-indigo-700">Two-way fit</p>
          <h2 className="font-semibold">Score weights</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Candidate → role measures how well your evidence covers the job.
            Role → you measures how well the job matches your stated goals and
            constraints.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={busy || draftIsDefault}
            onClick={() => {
              setDraft({ ...DEFAULT_SCORING_WEIGHTS });
              setQueuePreview(null);
              setPreviewError('');
            }}
          >
            <RotateCcw /> Reset defaults
          </Button>
          <Button
            variant="outline"
            disabled={busy || previewBusy || total !== 100}
            onClick={() => void previewQueue()}
          >
            <Eye /> {previewBusy ? 'Comparing queue…' : 'Preview current queue'}
          </Button>
          <Button
            disabled={busy || !changed || total !== 100}
            onClick={() =>
              void onSave(
                { ...profile, scoring_weights: draft },
                'Approved scoring weights saved locally. Rankings have been refreshed.',
              )
            }
          >
            <Save /> Save approved weights
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">
          <span className="font-semibold">Candidate → role</span>{' '}
          {scoringDirectionTotal(draft, 'candidate-to-role')} points
        </div>
        <div className="rounded-xl bg-indigo-50 p-3 text-sm text-indigo-900">
          <span className="font-semibold">Role → you</span>{' '}
          {scoringDirectionTotal(draft, 'role-to-candidate')} points
        </div>
      </div>

      <fieldset className="mt-5 grid gap-3 md:grid-cols-2">
        <legend className="sr-only">Scoring component weights</legend>
        {SCORING_COMPONENTS.map((component) => (
          <label
            key={component.key}
            htmlFor={`score-weight-${component.key}`}
            className="grid grid-cols-[minmax(0,1fr)_5rem] items-center gap-3 rounded-xl border border-slate-200 p-3"
          >
            <span>
              <span className="block text-sm font-medium">
                {component.label}
              </span>
              <span className="block text-xs leading-4 text-slate-500">
                {component.description}
              </span>
            </span>
            <Input
              id={`score-weight-${component.key}`}
              type="number"
              min={0}
              max={100}
              step={1}
              value={draft[component.key]}
              onChange={(event) => update(component.key, event.target.value)}
              aria-label={`${component.label} weight`}
            />
          </label>
        ))}
      </fieldset>

      <p
        className={`mt-3 text-sm font-medium ${total === 100 ? 'text-emerald-700' : 'text-red-700'}`}
        role={total === 100 ? 'status' : 'alert'}
      >
        Total: {total}/100
        {total === 100
          ? '. Ready to preview or save.'
          : '. Adjust the weights to total 100.'}
      </p>

      <div className="mt-6 border-t border-slate-100 pt-5">
        <h3 className="font-semibold">Preview with synthetic roles</h3>
        <p className="mt-1 text-sm text-slate-500">
          These examples contain no resume or employer data. They show exactly
          which components move before you save.
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-2" aria-live="polite">
          {SYNTHETIC_SCORE_EXAMPLES.map((example) => {
            const before = syntheticScore(current, example.coverage);
            const after = syntheticScore(draft, example.coverage);
            const delta = after.score - before.score;
            return (
              <article
                key={example.name}
                className="rounded-xl border border-slate-200 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-semibold">{example.name}</h4>
                    <p className="mt-1 text-xs leading-4 text-slate-500">
                      {example.summary}
                    </p>
                  </div>
                  <Badge variant="outline">
                    {before.score} → {after.score}{' '}
                    <span
                      className={
                        delta > 0
                          ? 'text-emerald-700'
                          : delta < 0
                            ? 'text-red-700'
                            : 'text-slate-500'
                      }
                    >
                      ({delta > 0 ? '+' : ''}
                      {delta})
                    </span>
                  </Badge>
                </div>
                <ul className="mt-3 space-y-1 text-xs text-slate-600">
                  {SCORING_COMPONENTS.filter(
                    ({ key }) =>
                      before.components[key] !== after.components[key],
                  ).map(({ key, label }) => (
                    <li key={key}>
                      {label}: {before.components[key]} →{' '}
                      {after.components[key]}
                    </li>
                  ))}
                  {!changed && <li>No component changes yet.</li>}
                </ul>
              </article>
            );
          })}
        </div>
      </div>

      <div className="mt-6 border-t border-slate-100 pt-5">
        <h3 className="font-semibold">Private current-queue preview</h3>
        <p className="mt-1 text-sm text-slate-500">
          Compare the top new roles using these tentative weights. The preview
          runs against data already on this Mac and does not save your changes.
        </p>
        {previewError && (
          <p className="mt-3 text-sm text-red-700" role="alert">
            {previewError}
          </p>
        )}
        {queuePreview && (
          <div className="mt-4" aria-live="polite">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <Badge variant="outline">
                {queuePreview.queue_size.toLocaleString()} new roles evaluated
              </Badge>
              <span>
                Tentative weights were not saved.
                {queuePreview.current_snapshot_reused
                  ? ' Current dashboard ranking reused.'
                  : ''}
                {queuePreview.candidate_set_reused
                  ? ' Eligible queue reused.'
                  : ' Eligible queue refreshed.'}
              </span>
            </div>
            <Table>
              <TableCaption>
                Current and proposed rank among the first 30 qualifying roles.
              </TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Role</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Rank</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queuePreview.rows.map((row) => {
                  const delta =
                    row.current_score === null || row.proposed_score === null
                      ? null
                      : row.proposed_score - row.current_score;
                  return (
                    <TableRow key={row.job_key}>
                      <TableCell className="min-w-64 whitespace-normal">
                        <span className="font-medium">{row.title}</span>
                        <span className="block text-xs text-slate-500">
                          {row.company}
                        </span>
                      </TableCell>
                      <TableCell>
                        {row.current_score ?? '—'} → {row.proposed_score ?? '—'}
                        {delta !== null && (
                          <span
                            className={`ml-1 ${
                              delta > 0
                                ? 'text-emerald-700'
                                : delta < 0
                                  ? 'text-red-700'
                                  : 'text-slate-500'
                            }`}
                          >
                            ({delta > 0 ? '+' : ''}
                            {delta})
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        {row.current_rank ? `#${row.current_rank}` : '30+'} →{' '}
                        {row.proposed_rank ? `#${row.proposed_rank}` : '30+'}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </section>
  );
}
