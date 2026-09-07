'use client';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Kbd, KbdGroup } from '@/components/ui/kbd';

export function ReviewShortcutBar({
  message,
  visibleCount,
  lastAddedSkill,
  busy,
  helpOpen,
  onHelpOpenChange,
  onUndo,
}: {
  message: string;
  visibleCount: number;
  lastAddedSkill: string | null;
  busy: boolean;
  helpOpen: boolean;
  onHelpOpenChange: (open: boolean) => void;
  onUndo: () => void;
}) {
  return (
    <>
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-5 py-2 text-sm text-slate-700 lg:px-10">
        <span className={message ? 'font-medium text-emerald-800' : ''}>
          {message ||
            'Keyboard: J/↓ next · K/↑ previous · S save · R reject · A applied'}
        </span>
        {lastAddedSkill && (
          <Button size="sm" variant="outline" disabled={busy} onClick={onUndo}>
            Undo
          </Button>
        )}
        <Button
          size="xs"
          variant="ghost"
          onClick={() => onHelpOpenChange(true)}
        >
          Shortcut help <Kbd>?</Kbd>
        </Button>
        <output className="sr-only" aria-live="polite">
          {message || `${visibleCount} roles shown.`}
        </output>
      </div>
      <Dialog open={helpOpen} onOpenChange={onHelpOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Keyboard review shortcuts</DialogTitle>
            <DialogDescription>
              Navigate and record decisions without leaving the role queue.
            </DialogDescription>
          </DialogHeader>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt>
              <KbdGroup>
                <Kbd>J</Kbd>
                <span>/</span>
                <Kbd>↓</Kbd>
              </KbdGroup>
            </dt>
            <dd>Select next visible role</dd>
            <dt>
              <KbdGroup>
                <Kbd>K</Kbd>
                <span>/</span>
                <Kbd>↑</Kbd>
              </KbdGroup>
            </dt>
            <dd>Select previous visible role</dd>
            <dt>
              <Kbd>S</Kbd>
            </dt>
            <dd>Save selected role</dd>
            <dt>
              <Kbd>R</Kbd>
            </dt>
            <dd>Reject selected role</dd>
            <dt>
              <Kbd>A</Kbd>
            </dt>
            <dd>Mark selected role applied</dd>
            <dt>
              <Kbd>Esc</Kbd>
            </dt>
            <dd>Clear the current selection</dd>
          </dl>
          <DialogFooter>
            <Button onClick={() => onHelpOpenChange(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
