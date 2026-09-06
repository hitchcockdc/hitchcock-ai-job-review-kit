'use client';

import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, FileText, FileUp, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Job, TailoredDraft } from './dashboard-types';

const API = '';

export function TailorResume({ job }: { job: Job }) {
  const [draft, setDraft] = useState<TailoredDraft | null>(null);
  const [message, setMessage] = useState('');
  const [working, setWorking] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [stage, setStage] = useState<1 | 2 | 3>(1);
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);
  const resultRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (draft)
      resultRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
  }, [draft]);
  const request = async (action: 'draft' | 'save' | 'generate') => {
    setWorking(true);
    setMessage('');
    try {
      const response = await fetch(`${API}/api/resume-tailor/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_key: job.key,
          plan_id: draft?.plan_id,
          selected_experience_bullets: selectedEvidence,
        }),
      });
      const payload = (await response.json()) as {
        draft?: TailoredDraft;
        download_url?: string;
        error?: string;
      };
      if (!response.ok)
        throw new Error(
          payload.error || 'Could not create the tailored draft.',
        );
      if (!payload.draft)
        throw new Error('The local API returned no tailored draft.');
      const nextDraft = payload.draft;
      setDraft(nextDraft);
      setSelectedEvidence(nextDraft.selected_experience_bullets ?? []);
      setDownloadUrl(
        payload.download_url ? `${API}${payload.download_url}` : null,
      );
      if (action === 'draft') setStage(2);
      if (action === 'save') setStage(3);
      const applied = nextDraft.experience_bullets_applied ?? [];
      setMessage(
        action === 'generate'
          ? `Tailored DOCX created privately. Changed: summary${nextDraft.reordered_core_expertise.length ? ', Core Expertise' : ''}${applied.length ? `, and ${applied.length} selected experience bullet${applied.length === 1 ? '' : 's'}` : ''}. Your original is unchanged.`
          : action === 'save'
            ? 'Approved tailoring plan saved locally. Your original resume was not replaced.'
            : 'Draft ready below. Review the evidence, then save the plan or generate a DOCX.',
      );
    } catch (cause) {
      setMessage(
        cause instanceof Error
          ? cause.message
          : 'Could not create the tailored draft.',
      );
    } finally {
      setWorking(false);
    }
  };
  return (
    <section className="mt-5 rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm">
      <p className="text-xs font-semibold uppercase tracking-[.12em] text-indigo-700">
        Tailor your resume
      </p>
      <p className="mt-1 text-xs leading-5 text-indigo-950">
        Create a private, evidence-only version for this role. Your source
        document is never replaced.
      </p>
      <ol className="mt-3 grid grid-cols-3 gap-1 text-center text-[11px] font-semibold">
        <li
          className={
            stage >= 1
              ? 'rounded bg-indigo-600 px-1 py-1 text-white'
              : 'rounded bg-slate-100 px-1 py-1 text-slate-500'
          }
        >
          1. Create
        </li>
        <li
          className={
            stage >= 2
              ? 'rounded bg-indigo-600 px-1 py-1 text-white'
              : 'rounded bg-slate-100 px-1 py-1 text-slate-500'
          }
        >
          2. Review
        </li>
        <li
          className={
            stage >= 3
              ? 'rounded bg-indigo-600 px-1 py-1 text-white'
              : 'rounded bg-slate-100 px-1 py-1 text-slate-500'
          }
        >
          3. Generate
        </li>
      </ol>
      <Button
        className="mt-3 w-full"
        variant="outline"
        disabled={working}
        onClick={() => void request('draft')}
      >
        <FileText /> {working ? 'Preparing draft…' : '1. Create tailored draft'}
      </Button>
      {message && (
        <p
          aria-live="polite"
          className="mt-3 rounded-lg border border-indigo-200 bg-white p-2 text-xs font-semibold text-indigo-900"
        >
          {message}
        </p>
      )}
      {draft && (
        <div
          ref={resultRef}
          className="mt-4 space-y-4 rounded-xl border border-indigo-200 bg-white p-3"
        >
          <div className="flex items-center gap-2 text-sm font-semibold text-indigo-950">
            <CheckCircle2 size={16} className="text-emerald-600" /> 2. Review
            your tailored draft
          </div>
          <div>
            <p className="text-xs font-semibold text-emerald-800">
              Emphasize existing skills
            </p>
            <div className="mt-2 flex flex-wrap gap-1">
              {draft.emphasize_existing_skills.length ? (
                draft.emphasize_existing_skills.map((skill) => (
                  <span
                    key={skill}
                    className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800"
                  >
                    {skill}
                  </span>
                ))
              ) : (
                <span className="text-xs text-slate-600">
                  No direct role skills were found.
                </span>
              )}
            </div>
          </div>
          <details open>
            <summary className="cursor-pointer text-xs font-semibold text-indigo-900">
              Review existing resume evidence and proposed ordering
            </summary>
            <p className="mt-2 text-xs leading-5 text-slate-700">
              {draft.reviewer_instruction}
            </p>
            {draft.current_summary && (
              <>
                <p className="mt-2 text-xs font-semibold text-slate-700">
                  Current summary
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-700">
                  {draft.current_summary}
                </p>
                <p className="mt-2 text-xs font-semibold text-slate-700">
                  Proposed summary order
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-700">
                  {draft.tailored_summary || draft.current_summary}
                </p>
                {!draft.summary_reordered && (
                  <p className="mt-1 text-xs text-slate-500">
                    The current summary already emphasizes the strongest
                    matching evidence.
                  </p>
                )}
              </>
            )}
            <p className="mt-2 text-xs font-semibold text-slate-700">
              Suggested core-expertise order
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-700">
              {draft.reordered_core_expertise.join(' · ') ||
                'No core-expertise section found.'}
            </p>
            <p className="mt-3 text-xs font-semibold text-slate-700">
              Select existing experience evidence for this plan
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Selections are saved with this role’s private plan. Selected
              bullets are reordered only within a recognized experience group.
            </p>
            <div className="mt-2 space-y-2">
              {draft.experience_bullet_options.length ? (
                draft.experience_bullet_options.map((line) => (
                  <label
                    key={line}
                    className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 p-2 text-xs leading-5 text-slate-700"
                  >
                    <input
                      type="checkbox"
                      checked={selectedEvidence.includes(line)}
                      onChange={() =>
                        setSelectedEvidence((current) =>
                          current.includes(line)
                            ? current.filter((item) => item !== line)
                            : [...current, line],
                        )
                      }
                    />
                    <span>{line}</span>
                  </label>
                ))
              ) : (
                <p className="text-xs text-slate-500">
                  No role-relevant experience statements were detected.
                </p>
              )}
            </div>
            {draft.skills_not_added.length > 0 && (
              <p className="mt-2 text-xs text-red-700">
                Not added: {draft.skills_not_added.join(', ')}
              </p>
            )}
          </details>
          <div className="grid gap-2">
            <Button
              variant="outline"
              disabled={working}
              onClick={() => void request('save')}
            >
              <Save /> Approve tailoring plan
            </Button>
            <Button
              disabled={working || stage < 3}
              onClick={() => void request('generate')}
            >
              <FileUp /> 3. Generate tailored DOCX
            </Button>
            {stage < 3 && (
              <p className="text-center text-xs text-slate-500">
                Approve the reviewed plan before generating a document.
              </p>
            )}
            {downloadUrl && (
              <a
                className="inline-flex justify-center rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-900"
                href={downloadUrl}
              >
                Download tailored DOCX
              </a>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
