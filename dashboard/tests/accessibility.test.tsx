import { fireEvent, render, screen } from '@testing-library/react';
import axe from 'axe-core';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import Home from '../app/page';
import type { Item, Profile } from '../app/dashboard-types';

const profile: Profile = {
  skills: ['Python'],
  skill_aliases: {},
  remote_ok: true,
  minimum_salary: 90_000,
  max_travel_percentage: null,
  locations: ['Denver', 'Colorado'],
  employment_types: ['full time'],
  title_priorities: ['software engineer'],
  eligible_countries: ['US'],
  work_authorized_countries: ['US'],
  consider_sponsorship_roles: false,
  excluded_terms: [],
};

const job: Item = {
  job: {
    key: 'fixture:accessible-role',
    title: 'Accessible Software Engineer',
    company: 'Example Technology',
    url: 'https://example.com/jobs/accessible-role',
    description: 'Build Python and REST API services.',
    location: 'Remote - United States',
    remote: true,
    country: 'US',
    countries: ['US'],
    regions: [],
    employment_type: 'Full time',
    salary_min: 110_000,
    salary_max: 145_000,
  },
  match: {
    score: 80,
    reasons: [
      'matched skills: Python',
      'role skills not yet in resume: REST API',
    ],
    evidence: [],
    matched_skills: ['Python'],
    missing_skills: ['REST API'],
    matched_required_skills: ['Python'],
    matched_preferred_skills: [],
    required_role_skills: ['Python'],
    buried_role_skills: ['REST API'],
    country_verification: 'verified',
    authorization_verification: 'verified',
    matched_role_skill_count: 1,
    role_skill_count: 2,
    role_skill_contexts: [],
    score_breakdown: {},
  },
  status: 'new',
};

async function expectNoAccessibilityViolations() {
  const results = await axe.run(document.body, {
    rules: {
      // happy-dom does not calculate rendered color contrast. Browser visual checks
      // cover the color-coded cards and skill pills separately.
      'color-contrast': { enabled: false },
    },
  });
  expect(
    results.violations,
    results.violations
      .map((violation) => `${violation.id}: ${violation.help}`)
      .join('\n'),
  ).toEqual([]);
}

describe('dashboard accessibility', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.href
              : input.url;
        if (url.startsWith('/api/jobs')) {
          return Response.json({
            jobs: [job],
            meta: { ranking_ms: 5, cached: false },
          });
        }
        if (url === '/api/stats') {
          return Response.json({
            counts: { new: 1, saved: 0, rejected: 0, applied: 0 },
            activity: { last_fetch_at: null },
            sources: [],
          });
        }
        if (url === '/api/config') {
          return Response.json({
            profile,
            resume: {
              present: false,
              name: null,
              source_format: null,
              docx_present: false,
              pdf_present: false,
            },
            resume_draft: null,
            resume_text_preview: '',
          });
        }
        if (url === '/api/decisions') return Response.json({ decisions: [] });
        if (url === '/api/applications') {
          return Response.json({ applications: [] });
        }
        if (url === '/api/learning') {
          return Response.json({
            terms: { positive: [], negative: [] },
            ignored: [],
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  test('review queue and skill confirmation have accessible structure', async () => {
    render(<Home />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: /Accessible Software Engineer/,
      }),
    );

    expect(
      screen.getByRole('link', { name: /Open employer application/ }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'REST API +' }));
    expect(
      screen.getByRole('dialog', { name: 'Add REST API to your profile?' }),
    ).toBeTruthy();

    await expectNoAccessibilityViolations();
  });

  test('configuration controls have accessible names', async () => {
    render(<Home />);
    fireEvent.click(screen.getByRole('button', { name: 'Configuration' }));

    expect(
      await screen.findByRole('heading', { name: 'Tune the job search' }),
    ).toBeTruthy();
    expect(
      screen.getByRole('spinbutton', { name: 'Minimum salary' }),
    ).toBeTruthy();
    expect(
      screen.getByRole('textbox', {
        name: 'Target job countries or regions',
      }),
    ).toBeTruthy();

    await expectNoAccessibilityViolations();
  });
});
