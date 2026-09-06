'use client';

import { BriefcaseBusiness, RefreshCw, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

type DashboardHeaderProps = {
  view: 'review' | 'settings';
  primaryStatus: string;
  secondaryStatus: string;
  onToggleSettings: () => void;
  onRefresh: () => void;
};

export function DashboardHeader({
  view,
  primaryStatus,
  secondaryStatus,
  onToggleSettings,
  onRefresh,
}: DashboardHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-5 py-5 lg:px-10">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-indigo-600 text-white">
            <BriefcaseBusiness size={21} />
          </div>
          <div>
            <p className="text-lg font-semibold">Job review desk</p>
            <p className="text-sm text-slate-500">
              Local, private, human-in-the-loop
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant={view === 'settings' ? 'outline' : 'ghost'}
            onClick={onToggleSettings}
          >
            <Settings2 /> Configuration
          </Button>
          <Button variant="outline" onClick={onRefresh}>
            <RefreshCw /> Refresh
          </Button>
        </div>
      </div>
      <div className="mx-auto flex max-w-[1600px] justify-between border-t border-slate-100 px-5 py-2 text-xs text-slate-500 lg:px-10">
        <span>{primaryStatus}</span>
        <span>{secondaryStatus}</span>
      </div>
    </header>
  );
}
