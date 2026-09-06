'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type Application = {
  job_key: string;
  title?: string;
  company?: string;
  url?: string;
  note: string;
  applied_at: string;
  follow_up_date: string;
  reminder_note: string;
};

const API = '';
const dateTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));

export function ApplicationTracker() {
  const [applications, setApplications] = useState<Application[]>([]);
  const load = useCallback(async () => {
    const response = await fetch(`${API}/api/applications`);
    if (response.ok)
      setApplications(
        ((await response.json()) as { applications: Application[] })
          .applications,
      );
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const update = (jobKey: string, values: Partial<Application>) =>
    setApplications((current) =>
      current.map((item) =>
        item.job_key === jobKey ? { ...item, ...values } : item,
      ),
    );
  const save = async (application: Application) => {
    await fetch(`${API}/api/application-followups`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_key: application.job_key,
        follow_up_date: application.follow_up_date,
        reminder_note: application.reminder_note,
      }),
    });
    await load();
  };
  return (
    <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <summary className="cursor-pointer font-semibold">
        Application tracker{' '}
        <span className="ml-2 text-sm font-normal text-slate-500">
          Applied roles, dates, and follow-ups
        </span>
      </summary>
      {applications.length ? (
        <div className="mt-4 space-y-3">
          {applications.map((application) => (
            <div
              key={`${application.job_key}-${application.applied_at}`}
              className="rounded-xl border border-slate-100 p-3 text-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">
                  {application.title || application.job_key}
                </span>
                {application.url && (
                  <a
                    href={application.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-medium text-indigo-700"
                  >
                    Application link
                  </a>
                )}
              </div>
              <p className="text-xs text-slate-500">
                {application.company ? `${application.company} · ` : ''}Applied{' '}
                {dateTime(application.applied_at)}
              </p>
              <div className="mt-2 grid gap-2 md:grid-cols-[180px_1fr_auto]">
                <Input
                  type="date"
                  value={application.follow_up_date}
                  onChange={(event) =>
                    update(application.job_key, {
                      follow_up_date: event.target.value,
                    })
                  }
                />
                <Input
                  value={application.reminder_note}
                  onChange={(event) =>
                    update(application.job_key, {
                      reminder_note: event.target.value,
                    })
                  }
                  placeholder="Follow-up reminder"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void save(application)}
                >
                  Save
                </Button>
              </div>
              {application.note && (
                <p className="mt-2 text-xs text-slate-600">
                  Application note: {application.note}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          No applied roles yet. When you mark a role Applied, its date, employer
          link, and decision note appear here.
        </p>
      )}
    </details>
  );
}
