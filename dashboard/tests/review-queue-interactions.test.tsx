import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import Home from '../app/page';
import type { Item, Match } from '../app/dashboard-types';

function match(
  countryVerification: string,
  authorizationVerification: string,
): Match {
  return {
    score: 70,
    reasons: ['work location match'],
    evidence: [],
    matched_skills: ['Python'],
    missing_skills: [],
    matched_required_skills: ['Python'],
    matched_preferred_skills: [],
    required_role_skills: ['Python'],
    buried_role_skills: [],
    country_verification: countryVerification,
    authorization_verification: authorizationVerification,
    matched_role_skill_count: 1,
    role_skill_count: 1,
    role_skill_contexts: [],
    score_breakdown: {},
  };
}

function item(
  key: string,
  title: string,
  countryVerification: string,
  authorizationVerification: string,
): Item {
  return {
    job: {
      key,
      title,
      company: 'Example',
      url: `https://example.com/${key}`,
      description: 'Build services with Python.',
      location: countryVerification === 'verified' ? 'United States' : 'Remote',
      remote: true,
      country: countryVerification === 'verified' ? 'US' : '',
      countries: countryVerification === 'verified' ? ['US'] : [],
      regions: [],
      employment_type: 'Full time',
      salary_min: null,
      salary_max: null,
    },
    match: match(countryVerification, authorizationVerification),
    status: 'new',
  };
}

describe('review queue interactions', () => {
  beforeEach(() => {
    const jobs = [
      item('verified', 'Verified Architect', 'verified', 'verified'),
      item(
        'unknown',
        'Confirmation Architect',
        'unknown',
        'sponsorship_required',
      ),
    ];
    jobs[0].job.description =
      'Lead architecture.&amp;nbsp;\\</p> \\&lt;p&gt;\\&lt;br&gt;Improve delivery &amp;amp; reliability.';
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
            jobs,
            meta: { ranking_ms: 5, cached: false },
          });
        }
        if (url === '/api/stats') {
          return Response.json({
            counts: { new: 2, saved: 0, rejected: 0, applied: 0 },
            activity: { last_fetch_at: null },
            sources: [],
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  test('cross-filters counts, cards, and selected role', async () => {
    render(<Home />);

    await screen.findByRole('button', { name: 'All eligible 2' });
    expect(
      screen.getByRole('button', { name: 'Location verified 1' }),
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: 'Needs confirmation 1' }),
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: 'All authorization 2' }),
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Authorized 1' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sponsorship 1' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /Verified Architect/ }));
    expect(
      screen.getByRole('link', { name: /Open employer application/ }),
    ).toBeTruthy();
    expect(
      screen.getAllByText('Lead architecture. Improve delivery & reliability.')
        .length,
    ).toBeGreaterThanOrEqual(2);

    fireEvent.click(
      screen.getByRole('button', { name: 'Needs confirmation 1' }),
    );
    expect(screen.getAllByText('Work-location filter updated.').length).toBe(2);
    await waitFor(() => {
      expect(
        screen.queryByRole('link', { name: /Open employer application/ }),
      ).toBeNull();
    });
    expect(
      screen.queryByRole('button', { name: /Verified Architect/ }),
    ).toBeNull();
    expect(
      screen.getByRole('button', { name: /Confirmation Architect/ }),
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Authorized 0' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sponsorship 1' })).toBeTruthy();

    fireEvent.click(
      screen.getByRole('button', { name: /Confirmation Architect/ }),
    );
    expect(
      screen.getByRole('link', { name: /Open employer application/ }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Authorized 0' }));
    await waitFor(() => {
      expect(
        screen.queryByRole('link', { name: /Open employer application/ }),
      ).toBeNull();
    });
    expect(
      screen.queryByRole('button', { name: /Confirmation Architect/ }),
    ).toBeNull();
  });

  test('supports keyboard navigation, review shortcuts, and mobile selection context', async () => {
    render(<Home />);
    await screen.findByRole('button', { name: /Verified Architect/ });

    const mobileFilters = screen.getByRole('button', {
      name: 'More filters Show',
    });
    expect(mobileFilters.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(mobileFilters);
    expect(mobileFilters.getAttribute('aria-expanded')).toBe('true');

    fireEvent.keyDown(window, { key: 'j' });
    const verified = screen.getByRole('button', {
      name: /Verified Architect/,
    });
    expect(verified.getAttribute('aria-current')).toBe('true');
    expect(screen.getByRole('link', { name: 'Review selected' })).toBeTruthy();
    expect(
      screen.getAllByText('Selected Verified Architect, 1 of 2.').length,
    ).toBe(2);

    fireEvent.keyDown(window, { key: 'ArrowDown' });
    expect(
      screen
        .getByRole('button', { name: /Confirmation Architect/ })
        .getAttribute('aria-current'),
    ).toBe('true');
    fireEvent.keyDown(window, { key: 'k' });
    expect(verified.getAttribute('aria-current')).toBe('true');

    fireEvent.keyDown(window, { key: '?' });
    expect(
      screen.getByRole('dialog', { name: 'Keyboard review shortcuts' }),
    ).toBeTruthy();
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: 'Keyboard review shortcuts' }),
      ).toBeNull();
    });

    fireEvent.keyDown(window, { key: 's' });
    expect(
      (
        await screen.findAllByText(
          /Saved recorded\. Now reviewing Confirmation Architect\./,
        )
      ).length,
    ).toBe(2);
    await waitFor(() => {
      expect(document.activeElement?.textContent).toContain(
        'Confirmation Architect',
      );
    });
  });
});
