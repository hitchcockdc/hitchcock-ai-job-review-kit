'use client';

import {
  ChangeEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DashboardHeader } from './dashboard-header';
import { SettingsPanel } from './settings-panel';
import {
  countAuthorizationVerification,
  countLocationVerification,
  filterQueueItems,
  nextQueueItemAfterReview,
} from './review-queue-state';
import { SkillGroup } from './role-skills';
import { ReviewQueue } from './review-queue';
import { RoleDetailPanel } from './role-detail-panel';
import type {
  AuthorizationVerificationFilter,
  Config,
  Decision,
  Item,
  LocationVerificationFilter,
  Profile,
  QueueMeta,
  Stats,
  Status,
} from './dashboard-types';

// Relative requests let the local preview proxy serve the same private API path.
const API = '';
const labels: Record<Status, string> = {
  new: 'New roles',
  saved: 'Saved',
  rejected: 'Rejected',
  applied: 'Applied',
};
const dateTime = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(value))
    : 'Not yet fetched';
function scoreParts(breakdown: Record<string, number>) {
  return [
    ['Required skills', breakdown.required_skills, 30],
    ['Role skills', breakdown.role_skills, 25],
    ['Target title', breakdown.title_target, 20],
    ['Title priority', breakdown.priority, 10],
    ['Work location', breakdown.work_location, 5],
    ['Other preferences', breakdown.preferences, 5],
    ['Industry', breakdown.industry, 5],
    ...(breakdown.decision_learning
      ? [['Learning', breakdown.decision_learning, 15]]
      : []),
  ] as [string, number | undefined, number][];
}

export default function Home() {
  const [view, setView] = useState<'review' | 'settings'>('review');
  const [status, setStatus] = useState<Status>('new');
  const [items, setItems] = useState<Item[]>([]);
  const [stats, setStats] = useState<Stats>({
    counts: {},
    activity: { last_fetch_at: null },
    sources: [],
  });
  const [selected, setSelected] = useState<Item | null>(null);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [config, setConfig] = useState<Config | null>(null);
  const [profileJson, setProfileJson] = useState('');
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [message, setMessage] = useState('');
  const [reviewMessage, setReviewMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingSkill, setPendingSkill] = useState<string | null>(null);
  const [lastAddedSkill, setLastAddedSkill] = useState<string | null>(null);
  const [coverageMinimum, setCoverageMinimum] = useState(0);
  const [locationVerification, setLocationVerification] =
    useState<LocationVerificationFilter>('all');
  const [authorizationVerification, setAuthorizationVerification] =
    useState<AuthorizationVerificationFilter>('all');
  const [queueMeta, setQueueMeta] = useState<QueueMeta | null>(null);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueLoaded, setQueueLoaded] = useState(false);
  const queuedRefresh = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    setError('');
    setQueueLoading(true);
    try {
      const [jobsResponse, statsResponse] = await Promise.all([
        fetch(`${API}/api/jobs?status=${status}&limit=50`),
        fetch(`${API}/api/stats`),
      ]);
      if (!jobsResponse.ok || !statsResponse.ok)
        throw new Error('The local dashboard API is not running.');
      const jobs = (await jobsResponse.json()) as {
        jobs: Item[];
        meta?: QueueMeta;
      };
      setItems(jobs.jobs);
      setQueueMeta(jobs.meta ?? null);
      setStats(await statsResponse.json());
      setSelected(
        (current) =>
          (current &&
            jobs.jobs.find((item) => item.job.key === current.job.key)) ||
          null,
      );
      setQueueLoaded(true);
      return jobs.jobs;
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not load roles.',
      );
      return [];
    } finally {
      setQueueLoading(false);
    }
  }, [status]);
  const loadSettings = useCallback(async (showDraft = false) => {
    try {
      const [configResponse, decisionsResponse] = await Promise.all([
        fetch(`${API}/api/config`),
        fetch(`${API}/api/decisions`),
      ]);
      if (!configResponse.ok || !decisionsResponse.ok)
        throw new Error('Could not load local configuration.');
      const next = (await configResponse.json()) as Config;
      setConfig(next);
      setProfileJson(
        JSON.stringify(
          showDraft && next.resume_draft ? next.resume_draft : next.profile,
          null,
          2,
        ),
      );
      const decisionPayload = (await decisionsResponse.json()) as {
        decisions: Decision[];
      };
      setDecisions(decisionPayload.decisions);
    } catch (cause) {
      setMessage(
        cause instanceof Error ? cause.message : 'Could not load settings.',
      );
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  useEffect(() => {
    const timer = window.setInterval(() => void refresh(), 60000);
    return () => window.clearInterval(timer);
  }, [refresh]);
  useEffect(
    () => () => {
      if (queuedRefresh.current) window.clearTimeout(queuedRefresh.current);
    },
    [],
  );
  useEffect(() => {
    if (view !== 'settings') return;
    const timer = window.setTimeout(() => void loadSettings(), 0);
    return () => window.clearTimeout(timer);
  }, [view, loadSettings]);

  const review = useCallback(
    async (nextStatus: Exclude<Status, 'new'>) => {
      if (!selected) return;
      setBusy(true);
      setError('');
      try {
        const response = await fetch(
          `${API}/api/jobs/${encodeURIComponent(selected.job.key)}/review`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: nextStatus, note }),
          },
        );
        const payload = (await response.json()) as { error?: string };
        if (!response.ok)
          throw new Error(
            payload.error || 'Could not record the review decision.',
          );
        setNote('');
        const next = nextQueueItemAfterReview(
          items,
          selected.job.key,
          coverageMinimum,
          locationVerification,
          authorizationVerification,
        );
        const remaining = items.filter(
          (item) => item.job.key !== selected.job.key,
        );
        setItems(remaining);
        setSelected(next);
        setStats((current) =>
          status === nextStatus
            ? current
            : {
                ...current,
                counts: {
                  ...current.counts,
                  [status]: Math.max(0, (current.counts[status] ?? 1) - 1),
                  [nextStatus]: (current.counts[nextStatus] ?? 0) + 1,
                },
              },
        );
        setReviewMessage(
          `${labels[nextStatus]} recorded. ${next ? `Now reviewing ${next.job.title}.` : 'No more roles in this queue.'}`,
        );
        if (queuedRefresh.current) window.clearTimeout(queuedRefresh.current);
        queuedRefresh.current = window.setTimeout(() => {
          queuedRefresh.current = null;
          void refresh();
        }, 1500);
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : 'Could not record the review decision.',
        );
      } finally {
        setBusy(false);
      }
    },
    [
      authorizationVerification,
      coverageMinimum,
      items,
      locationVerification,
      note,
      refresh,
      selected,
      status,
    ],
  );
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        !selected ||
        busy ||
        ['INPUT', 'TEXTAREA'].includes((event.target as HTMLElement)?.tagName)
      )
        return;
      const action = ({ s: 'saved', r: 'rejected', a: 'applied' } as const)[
        event.key.toLowerCase()
      ];
      if (action) {
        event.preventDefault();
        void review(action);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selected, busy, review]);
  async function saveProfile(profile: Profile, confirmation: string) {
    setBusy(true);
    setMessage('');
    try {
      const response = await fetch(`${API}/api/config/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile }),
      });
      const payload = (await response.json()) as {
        error?: string;
        profile?: Profile;
      };
      if (!response.ok)
        throw new Error(payload.error || 'Could not save configuration.');
      if (!payload.profile)
        throw new Error('The local API returned no updated profile.');
      const updatedProfile = payload.profile;
      setConfig((current) =>
        current ? { ...current, profile: updatedProfile } : current,
      );
      setProfileJson(JSON.stringify(updatedProfile, null, 2));
      setMessage(confirmation);
      await refresh();
    } catch (cause) {
      setMessage(
        cause instanceof Error
          ? cause.message
          : 'Could not save configuration.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function addSkillToProfile(skill: string) {
    setBusy(true);
    setError('');
    setReviewMessage('');
    try {
      const configResponse = await fetch(`${API}/api/config`);
      if (!configResponse.ok)
        throw new Error('Could not load your local profile.');
      const current = (await configResponse.json()) as Config;
      if (
        current.profile.skills.some(
          (existing) => existing.toLowerCase() === skill.toLowerCase(),
        )
      ) {
        setReviewMessage(`${skill} is already in your profile.`);
        return;
      }
      const profile = {
        ...current.profile,
        skills: [...current.profile.skills, skill],
      };
      const response = await fetch(`${API}/api/config/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile }),
      });
      const payload = (await response.json()) as {
        error?: string;
        profile?: Profile;
      };
      if (!response.ok)
        throw new Error(
          payload.error || 'Could not add the skill to your profile.',
        );
      if (!payload.profile)
        throw new Error('The local API returned no updated profile.');
      const updatedProfile = payload.profile;
      setConfig((existing) =>
        existing ? { ...existing, profile: updatedProfile } : existing,
      );
      setProfileJson(JSON.stringify(updatedProfile, null, 2));
      await refresh();
      setLastAddedSkill(skill);
      setReviewMessage(
        `${skill} added to your local profile. Rankings have been refreshed.`,
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Could not add the skill to your profile.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function undoSkillAddition() {
    if (!lastAddedSkill) return;
    setBusy(true);
    setError('');
    try {
      const configResponse = await fetch(`${API}/api/config`);
      if (!configResponse.ok)
        throw new Error('Could not load your local profile.');
      const current = (await configResponse.json()) as Config;
      const profile = {
        ...current.profile,
        skills: current.profile.skills.filter(
          (skill) => skill.toLowerCase() !== lastAddedSkill.toLowerCase(),
        ),
      };
      const response = await fetch(`${API}/api/config/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile }),
      });
      const payload = (await response.json()) as {
        error?: string;
        profile?: Profile;
      };
      if (!response.ok)
        throw new Error(payload.error || 'Could not undo the skill addition.');
      if (!payload.profile)
        throw new Error('The local API returned no updated profile.');
      const updatedProfile = payload.profile;
      setConfig((existing) =>
        existing ? { ...existing, profile: updatedProfile } : existing,
      );
      setProfileJson(JSON.stringify(updatedProfile, null, 2));
      await refresh();
      setReviewMessage(`${lastAddedSkill} removed from your local profile.`);
      setLastAddedSkill(null);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Could not undo the skill addition.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function uploadResume(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setMessage('Choose a resume smaller than 10 MB.');
      return;
    }
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setMessage('Choose a DOCX or PDF resume.');
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let text = '';
      for (const byte of bytes) text += String.fromCharCode(byte);
      const response = await fetch(`${API}/api/config/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          content_base64: btoa(text),
        }),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok)
        throw new Error(payload.error || 'Could not save resume.');
      setMessage(
        `${file.name.endsWith('.docx') ? 'DOCX selected as the preferred tailoring source.' : 'PDF resume loaded.'} Review the extracted changes below before saving.`,
      );
      await loadSettings(true);
    } catch (cause) {
      setMessage(
        cause instanceof Error ? cause.message : 'Could not save resume.',
      );
    } finally {
      setBusy(false);
      event.target.value = '';
    }
  }
  const reasons = useMemo(
    () =>
      selected?.match.reasons.filter(
        (reason) => !reason.startsWith('resume evidence:'),
      ) ?? [],
    [selected],
  );
  const visibleItems = useMemo(
    () =>
      filterQueueItems(
        items,
        coverageMinimum,
        locationVerification,
        authorizationVerification,
      ),
    [items, coverageMinimum, locationVerification, authorizationVerification],
  );
  const locationVerificationCounts = useMemo(
    () =>
      countLocationVerification(
        items,
        coverageMinimum,
        authorizationVerification,
      ),
    [items, coverageMinimum, authorizationVerification],
  );
  const authorizationVerificationCounts = useMemo(
    () =>
      countAuthorizationVerification(
        items,
        coverageMinimum,
        locationVerification,
      ),
    [items, coverageMinimum, locationVerification],
  );
  const healthy = stats.sources.filter((source) => !source.error).length;

  return (
    <main className="min-h-screen bg-[#f7f8fa] text-slate-950">
      <DashboardHeader
        view={view}
        primaryStatus={
          queueLoading && !queueLoaded
            ? 'Connecting to the local queue…'
            : `Last source refresh: ${dateTime(stats.activity.last_fetch_at)}`
        }
        secondaryStatus={
          queueLoading && !queueLoaded
            ? 'Loading queue status…'
            : `${queueMeta ? `Queue ${queueMeta.cached ? 'reused locally' : 'ranked'} in ${(queueMeta.ranking_ms / 1000).toFixed(queueMeta.ranking_ms < 1000 ? 2 : 1)}s` : 'Queue timing unavailable'} · ${healthy}/${stats.sources.length} sources healthy${queueLoading ? ' · Refreshing…' : ''}`
        }
        onToggleSettings={() =>
          setView(view === 'settings' ? 'review' : 'settings')
        }
        onRefresh={() => void refresh()}
      />
      {reviewMessage && (
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-2 border-b border-emerald-200 bg-emerald-50 px-5 py-3 text-sm text-emerald-900 lg:px-10">
          <span>{reviewMessage}</span>
          {lastAddedSkill && (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void undoSkillAddition()}
            >
              Undo
            </Button>
          )}
          <span className="text-emerald-700">
            Shortcuts: S save · R reject · A applied
          </span>
        </div>
      )}
      {pendingSkill && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/30 p-5">
          <dialog
            open
            aria-modal="true"
            className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 className="text-lg font-semibold">
              Add {pendingSkill} to your profile?
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Use this only when the skill is genuinely supported by your
              experience but was omitted from the resume. It stays local and
              immediately updates ranking.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setPendingSkill(null)}>
                Cancel
              </Button>
              <Button
                disabled={busy}
                onClick={() => {
                  const skill = pendingSkill;
                  setPendingSkill(null);
                  void addSkillToProfile(skill);
                }}
              >
                Add skill
              </Button>
            </div>
          </dialog>
        </div>
      )}
      {view === 'settings' ? (
        <SettingsPanel
          config={config}
          stats={stats}
          decisions={decisions}
          profileJson={profileJson}
          setProfileJson={setProfileJson}
          message={message}
          busy={busy}
          onSave={saveProfile}
          onUpload={uploadResume}
        />
      ) : (
        <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-5 px-5 py-6 lg:grid-cols-[240px_minmax(0,1fr)_420px] lg:px-10">
          <ReviewQueue
            status={status}
            stats={stats}
            queueLoaded={queueLoaded}
            queueLoading={queueLoading}
            coverageMinimum={coverageMinimum}
            locationVerification={locationVerification}
            locationVerificationCounts={locationVerificationCounts}
            authorizationVerification={authorizationVerification}
            authorizationVerificationCounts={authorizationVerificationCounts}
            visibleItems={visibleItems}
            selectedKey={selected?.job.key}
            error={error}
            onStatusChange={setStatus}
            onCoverageMinimumChange={setCoverageMinimum}
            onLocationVerificationChange={(filter) => {
              setLocationVerification(filter);
              setSelected(null);
            }}
            onAuthorizationVerificationChange={(filter) => {
              setAuthorizationVerification(filter);
              setSelected(null);
            }}
            onSelect={setSelected}
          />
          <RoleDetailPanel
            selected={selected}
            reasons={reasons}
            note={note}
            busy={busy}
            onNoteChange={setNote}
            onReview={(nextStatus) => void review(nextStatus)}
            onMissingSkillClick={setPendingSkill}
          />
        </div>
      )}
      {view === 'review' && selected && (
        <section className="mx-auto mb-6 max-w-[1600px] rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm lg:px-10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
                Selected role score breakdown
              </p>
              <p className="text-sm text-slate-700">
                {selected.job.title} — {selected.match.score}/100
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {scoreParts(selected.match.score_breakdown).map(
                ([label, value, maximum]) => (
                  <Badge key={label} variant="outline">
                    {label}: {value ?? 0}/{maximum}
                  </Badge>
                ),
              )}
            </div>
          </div>
        </section>
      )}
      {view === 'review' && selected && (
        <section className="mx-auto mb-6 max-w-[1600px] rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm lg:px-10">
          <p className="text-xs font-semibold uppercase tracking-[.12em] text-slate-500">
            Role skills
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Use the red skill controls in the role details to update your local
            profile.
          </p>
          <div className="mt-4 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <SkillGroup
              label="Your matching skills"
              skills={selected.match.matched_skills}
              headingClassName="text-emerald-700"
              pillClassName="border-emerald-200 bg-emerald-50 text-emerald-700"
              empty="No resume skills detected in this role."
            />
            <SkillGroup
              label="Missing from resume"
              skills={selected.match.missing_skills}
              headingClassName="text-red-700"
              pillClassName="border-red-200 bg-red-50 text-red-700"
              empty="No concrete gaps detected."
            />
            <SkillGroup
              label="Required by role"
              skills={selected.match.required_role_skills}
              headingClassName="text-violet-700"
              pillClassName="border-violet-200 bg-violet-50 text-violet-700"
              empty="No required skills detected."
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
      )}
    </main>
  );
}
