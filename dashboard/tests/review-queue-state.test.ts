import { expect, test } from 'vitest';

import {
  countAuthorizationVerification,
  countLocationVerification,
  filterQueueItems,
  nextQueueItemAfterReview,
} from '../app/review-queue-state';
import type { Item } from '../app/dashboard-types';

function queueItem(
  key: string,
  matched: number,
  total: number,
  countryVerification = 'verified',
  authorizationVerification = 'verified',
): Item {
  return {
    job: { key },
    match: {
      matched_role_skill_count: matched,
      role_skill_count: total,
      country_verification: countryVerification,
      authorization_verification: authorizationVerification,
    },
    status: 'new',
  } as Item;
}

const queue = [
  queueItem('verified-strong', 4, 5),
  queueItem('unknown-strong', 3, 5, 'unknown', 'sponsorship_required'),
  queueItem('verified-weak', 2, 5, 'verified', 'unknown'),
  queueItem('unrestricted-strong', 5, 5, 'not_required'),
  queueItem('authorization-unknown', 3, 4, 'verified', 'unknown'),
];

test('location counts respect skill and authorization filters', () => {
  expect(countLocationVerification(queue, 50)).toEqual({
    all: 4,
    verified: 3,
    unknown: 1,
  });
  expect(countLocationVerification(queue, 50, 'sponsorship_required')).toEqual({
    all: 1,
    verified: 0,
    unknown: 1,
  });
});

test('authorization counts respect skill and location filters', () => {
  expect(countAuthorizationVerification(queue, 50)).toEqual({
    all: 4,
    verified: 2,
    sponsorship_required: 1,
    unknown: 1,
  });
  expect(countAuthorizationVerification(queue, 50, 'unknown')).toEqual({
    all: 1,
    verified: 0,
    sponsorship_required: 1,
    unknown: 0,
  });
});

test('skill, location, and authorization filters combine', () => {
  expect(
    filterQueueItems(queue, 75, 'verified', 'verified').map(
      (item) => item.job.key,
    ),
  ).toEqual(['verified-strong', 'unrestricted-strong']);
  expect(
    filterQueueItems(queue, 50, 'unknown', 'sponsorship_required').map(
      (item) => item.job.key,
    ),
  ).toEqual(['unknown-strong']);
  expect(
    filterQueueItems(queue, 75, 'verified', 'unknown').map(
      (item) => item.job.key,
    ),
  ).toEqual(['authorization-unknown']);
});

test('optimistic review advances within all active filters', () => {
  expect(
    nextQueueItemAfterReview(
      queue,
      'verified-strong',
      50,
      'verified',
      'verified',
    )?.job.key,
  ).toBe('unrestricted-strong');
  expect(
    nextQueueItemAfterReview(
      queue,
      'unrestricted-strong',
      50,
      'verified',
      'verified',
    )?.job.key,
  ).toBe('verified-strong');
  expect(
    nextQueueItemAfterReview(
      queue,
      'unknown-strong',
      50,
      'unknown',
      'sponsorship_required',
    ),
  ).toBeNull();
});
