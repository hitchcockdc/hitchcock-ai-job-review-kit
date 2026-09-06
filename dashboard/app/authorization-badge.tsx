import { Badge } from '@/components/ui/badge';

const authorizationPresentation: Record<
  string,
  { label: string; className: string; title: string }
> = {
  verified: {
    label: 'Authorized',
    className: 'border-teal-200 bg-teal-50 text-teal-800',
    title:
      'The role location matches a country in your work-authorization profile.',
  },
  sponsorship_required: {
    label: 'Sponsorship',
    className: 'border-violet-200 bg-violet-50 text-violet-800',
    title:
      'The location matches your search, but employer sponsorship may be required.',
  },
  unknown: {
    label: 'Auth confirm',
    className: 'border-amber-200 bg-amber-50 text-amber-800',
    title: 'The posting is not specific enough to verify work authorization.',
  },
  ineligible: {
    label: 'Auth conflict',
    className: 'border-red-200 bg-red-50 text-red-800',
    title:
      'The role conflicts with your work-authorization or sponsorship preferences.',
  },
  not_configured: {
    label: 'Set authorization',
    className: 'border-slate-200 bg-slate-50 text-slate-700',
    title:
      'Add work-authorized countries in Configuration to verify this separately.',
  },
};

export function AuthorizationBadge({ status }: { status?: string }) {
  const presentation =
    authorizationPresentation[status ?? 'not_configured'] ??
    authorizationPresentation.not_configured;
  return (
    <Badge
      variant="outline"
      className={presentation.className}
      title={presentation.title}
    >
      {presentation.label}
    </Badge>
  );
}
