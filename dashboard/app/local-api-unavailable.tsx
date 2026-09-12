'use client';

import { RefreshCw, ServerOff } from 'lucide-react';
import { Button } from '@/components/ui/button';

type LocalApiUnavailableProps = {
  onRetry: () => void;
};

export function LocalApiUnavailable({ onRetry }: LocalApiUnavailableProps) {
  return (
    <section
      aria-live="assertive"
      aria-labelledby="local-api-unavailable-title"
      className="mx-auto max-w-[1600px] px-4 py-4 sm:px-5 lg:px-10"
    >
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-950 shadow-sm">
        <div className="flex items-start gap-3">
          <ServerOff className="mt-0.5 shrink-0 text-amber-700" />
          <div>
            <h1 id="local-api-unavailable-title" className="font-semibold">
              The local dashboard service is not available
            </h1>
            <p className="mt-1 text-sm leading-5">
              Your private job data is still on this computer. Start the local
              API with <code>PYTHONPATH=src python3 -m get_a_job.dashboard_server --port 8765</code>, then retry.
            </p>
            <Button className="mt-4" variant="outline" onClick={onRetry}>
              <RefreshCw /> Retry connection
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
