import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { ScoreWeightSettings } from '../app/score-weight-settings';
import {
  DEFAULT_SCORING_WEIGHTS,
  SYNTHETIC_SCORE_EXAMPLES,
  scoringDirectionTotal,
  syntheticScore,
} from '../app/scoring';
import type { Profile } from '../app/dashboard-types';

const profile: Profile = {
  skills: ['Python'],
  skill_aliases: {},
  remote_ok: true,
  minimum_salary: null,
  max_travel_percentage: null,
  locations: [],
  employment_types: [],
  title_priorities: [],
  eligible_countries: ['US'],
  work_authorized_countries: ['US'],
  consider_sponsorship_roles: false,
  excluded_terms: [],
  scoring_weights: DEFAULT_SCORING_WEIGHTS,
};

describe('score weight comparison', () => {
  afterEach(() => vi.unstubAllGlobals());

  test('keeps the two scoring directions explicit and deterministic', () => {
    expect(
      scoringDirectionTotal(DEFAULT_SCORING_WEIGHTS, 'candidate-to-role'),
    ).toBe(55);
    expect(
      scoringDirectionTotal(DEFAULT_SCORING_WEIGHTS, 'role-to-candidate'),
    ).toBe(45);
    expect(
      syntheticScore(
        DEFAULT_SCORING_WEIGHTS,
        SYNTHETIC_SCORE_EXAMPLES[0].coverage,
      ).score,
    ).toBe(71);
  });

  test('previews component changes and saves only a 100-point allocation', () => {
    const onSave = vi.fn(async () => undefined);
    render(
      <ScoreWeightSettings profile={profile} busy={false} onSave={onSave} />,
    );

    expect(
      screen.getByText('Candidate → role').parentElement?.textContent,
    ).toBe('Candidate → role 55 points');
    expect(screen.getByText('Role → you').parentElement?.textContent).toBe(
      'Role → you 45 points',
    );
    const save = screen.getByRole('button', { name: 'Save approved weights' });
    expect((save as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(
      screen.getByRole('spinbutton', { name: 'Required skills weight' }),
      { target: { value: '35' } },
    );
    expect(screen.getByRole('alert').textContent).toContain('105/100');
    expect((save as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(
      screen.getByRole('spinbutton', { name: 'All role skills weight' }),
      { target: { value: '20' } },
    );
    expect(screen.getByRole('status').textContent).toContain('100/100');
    expect(screen.getByText('Required skills: 30 → 35')).toBeTruthy();
    expect(screen.getByText('All role skills: 23 → 18')).toBeTruthy();
    expect((save as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        scoring_weights: expect.objectContaining({
          required_skills: 35,
          role_skills: 20,
        }),
      }),
      expect.stringContaining('saved locally'),
    );
  });

  test('previews the local queue without saving tentative weights', async () => {
    const onSave = vi.fn(async () => undefined);
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            rows: [
              {
                job_key: 'test:1',
                title: 'Platform Architect',
                company: 'Example',
                current_score: 68,
                proposed_score: 72,
                current_rank: 4,
                proposed_rank: 2,
              },
            ],
            current_weights: DEFAULT_SCORING_WEIGHTS,
            proposed_weights: DEFAULT_SCORING_WEIGHTS,
            queue_size: 24,
            persisted: false,
            current_snapshot_reused: true,
            candidate_set_reused: true,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(
      <ScoreWeightSettings profile={profile} busy={false} onSave={onSave} />,
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Preview current queue' }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(await screen.findByText('Platform Architect')).toBeTruthy();
    expect(screen.getByText('68 → 72')).toBeTruthy();
    expect(screen.getByText('#4 → #2')).toBeTruthy();
    expect(
      screen.getByText(
        'Tentative weights were not saved. Current dashboard ranking reused. Eligible queue reused.',
      ),
    ).toBeTruthy();
    expect(onSave).not.toHaveBeenCalled();
  });

  test('saves named presets and restores one in a single action', () => {
    const onSave = vi.fn(async () => undefined);
    const savedProfile = {
      ...profile,
      scoring_presets: {
        'Previous allocation': {
          ...DEFAULT_SCORING_WEIGHTS,
          required_skills: 25,
          role_skills: 30,
        },
      },
    };
    render(
      <ScoreWeightSettings profile={savedProfile} busy={false} onSave={onSave} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Restore' }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        scoring_weights: expect.objectContaining({
          required_skills: 25,
          role_skills: 30,
        }),
      }),
      expect.stringContaining('Restored'),
    );

    fireEvent.change(screen.getByRole('textbox', { name: 'Preset name' }), {
      target: { value: 'Current experiment' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save preset' }));
    expect(onSave).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scoring_presets: expect.objectContaining({
          'Current experiment': DEFAULT_SCORING_WEIGHTS,
        }),
      }),
      expect.stringContaining('Saved'),
    );
  });
});
