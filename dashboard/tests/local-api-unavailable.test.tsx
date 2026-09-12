import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import Home from '../app/page';

describe('local API recovery', () => {
  afterEach(() => vi.unstubAllGlobals());

  test('hides stale queue content and offers a retry when the local API is offline', async () => {
    const fetch = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    vi.stubGlobal('fetch', fetch);

    render(<Home />);

    expect(
      await screen.findByRole('heading', {
        name: 'The local dashboard service is not available',
      }),
    ).toBeTruthy();
    expect(
      screen.queryByRole('list', { name: 'Roles available for review' }),
    ).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }));
    await waitFor(() => expect(fetch.mock.calls.length).toBeGreaterThan(2));
  });
});
