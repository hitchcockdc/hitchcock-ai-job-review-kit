import type { ScoringWeightKey, ScoringWeights } from './dashboard-types';

export const DEFAULT_SCORING_WEIGHTS: ScoringWeights = {
  required_skills: 30,
  role_skills: 25,
  title_target: 20,
  priority: 10,
  work_location: 5,
  preferences: 5,
  industry: 5,
};

export const SCORING_COMPONENTS: Array<{
  key: ScoringWeightKey;
  label: string;
  description: string;
  direction: 'candidate-to-role' | 'role-to-candidate';
}> = [
  {
    key: 'required_skills',
    label: 'Required skills',
    description: 'How much of the role’s explicit requirements you cover.',
    direction: 'candidate-to-role',
  },
  {
    key: 'role_skills',
    label: 'All role skills',
    description:
      'Your weighted coverage of capabilities throughout the posting.',
    direction: 'candidate-to-role',
  },
  {
    key: 'title_target',
    label: 'Target title',
    description: 'Whether the role matches one of your target titles.',
    direction: 'role-to-candidate',
  },
  {
    key: 'priority',
    label: 'Title priority',
    description: 'Whether the title is one of your highest-priority targets.',
    direction: 'role-to-candidate',
  },
  {
    key: 'work_location',
    label: 'Work location',
    description: 'Whether remote or local work matches your preferences.',
    direction: 'role-to-candidate',
  },
  {
    key: 'preferences',
    label: 'Other preferences',
    description:
      'Salary, employment, travel, geography, and authorization fit.',
    direction: 'role-to-candidate',
  },
  {
    key: 'industry',
    label: 'Industry',
    description:
      'Whether the employer and title align with your target industries.',
    direction: 'role-to-candidate',
  },
];

export const SYNTHETIC_SCORE_EXAMPLES = [
  {
    name: 'Skills-forward platform role',
    summary:
      'Excellent capability coverage, but only partial title and industry alignment.',
    coverage: {
      required_skills: 1,
      role_skills: 0.9,
      title_target: 0.25,
      priority: 0,
      work_location: 1,
      preferences: 1,
      industry: 0.5,
    },
  },
  {
    name: 'Preference-forward program role',
    summary:
      'Excellent title and work fit, with partial coverage of technical requirements.',
    coverage: {
      required_skills: 0.45,
      role_skills: 0.5,
      title_target: 1,
      priority: 1,
      work_location: 1,
      preferences: 1,
      industry: 1,
    },
  },
] satisfies Array<{
  name: string;
  summary: string;
  coverage: ScoringWeights;
}>;

export function scoringWeights(
  weights: ScoringWeights | undefined,
): ScoringWeights {
  return weights ? { ...weights } : { ...DEFAULT_SCORING_WEIGHTS };
}

export function scoringWeightTotal(weights: ScoringWeights): number {
  return Object.values(weights).reduce((total, value) => total + value, 0);
}

export function scoringDirectionTotal(
  weights: ScoringWeights,
  direction: 'candidate-to-role' | 'role-to-candidate',
): number {
  return SCORING_COMPONENTS.filter(
    (component) => component.direction === direction,
  ).reduce((total, component) => total + weights[component.key], 0);
}

export function syntheticScore(
  weights: ScoringWeights,
  coverage: ScoringWeights,
): { score: number; components: ScoringWeights } {
  const components = Object.fromEntries(
    SCORING_COMPONENTS.map(({ key }) => [
      key,
      Math.round(weights[key] * coverage[key]),
    ]),
  ) as ScoringWeights;
  return {
    score: Math.min(100, scoringWeightTotal(components)),
    components,
  };
}
