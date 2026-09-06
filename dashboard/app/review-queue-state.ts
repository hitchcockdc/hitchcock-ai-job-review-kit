import type {
  AuthorizationVerificationFilter,
  Item,
  LocationVerificationFilter,
} from './dashboard-types';

export type LocationVerificationCounts = Record<
  LocationVerificationFilter,
  number
>;
export type AuthorizationVerificationCounts = Record<
  AuthorizationVerificationFilter,
  number
>;

export function roleSkillCoverage(match: Item['match']) {
  return match.role_skill_count
    ? Math.round(
        (100 * (match.matched_role_skill_count ?? 0)) / match.role_skill_count,
      )
    : 0;
}

function locationVerificationBucket(
  item: Item,
): Exclude<LocationVerificationFilter, 'all'> {
  return item.match.country_verification === 'unknown' ? 'unknown' : 'verified';
}

function authorizationVerificationBucket(
  item: Item,
): Exclude<AuthorizationVerificationFilter, 'all'> {
  if (item.match.authorization_verification === 'verified') return 'verified';
  if (item.match.authorization_verification === 'sponsorship_required') {
    return 'sponsorship_required';
  }
  return 'unknown';
}

export function matchesQueueFilters(
  item: Item,
  coverageMinimum: number,
  locationVerification: LocationVerificationFilter,
  authorizationVerification: AuthorizationVerificationFilter = 'all',
) {
  return (
    roleSkillCoverage(item.match) >= coverageMinimum &&
    (locationVerification === 'all' ||
      locationVerificationBucket(item) === locationVerification) &&
    (authorizationVerification === 'all' ||
      authorizationVerificationBucket(item) === authorizationVerification)
  );
}

export function filterQueueItems(
  items: Item[],
  coverageMinimum: number,
  locationVerification: LocationVerificationFilter,
  authorizationVerification: AuthorizationVerificationFilter = 'all',
) {
  return items.filter((item) =>
    matchesQueueFilters(
      item,
      coverageMinimum,
      locationVerification,
      authorizationVerification,
    ),
  );
}

export function countLocationVerification(
  items: Item[],
  coverageMinimum: number,
  authorizationVerification: AuthorizationVerificationFilter = 'all',
): LocationVerificationCounts {
  const counts: LocationVerificationCounts = {
    all: 0,
    verified: 0,
    unknown: 0,
  };
  for (const item of items) {
    if (
      roleSkillCoverage(item.match) < coverageMinimum ||
      (authorizationVerification !== 'all' &&
        authorizationVerificationBucket(item) !== authorizationVerification)
    ) {
      continue;
    }
    counts.all += 1;
    counts[locationVerificationBucket(item)] += 1;
  }
  return counts;
}

export function countAuthorizationVerification(
  items: Item[],
  coverageMinimum: number,
  locationVerification: LocationVerificationFilter = 'all',
): AuthorizationVerificationCounts {
  const counts: AuthorizationVerificationCounts = {
    all: 0,
    verified: 0,
    sponsorship_required: 0,
    unknown: 0,
  };
  for (const item of items) {
    if (
      roleSkillCoverage(item.match) < coverageMinimum ||
      (locationVerification !== 'all' &&
        locationVerificationBucket(item) !== locationVerification)
    ) {
      continue;
    }
    counts.all += 1;
    counts[authorizationVerificationBucket(item)] += 1;
  }
  return counts;
}

export function nextQueueItemAfterReview(
  items: Item[],
  reviewedKey: string,
  coverageMinimum: number,
  locationVerification: LocationVerificationFilter,
  authorizationVerification: AuthorizationVerificationFilter = 'all',
) {
  const visibleItems = filterQueueItems(
    items,
    coverageMinimum,
    locationVerification,
    authorizationVerification,
  );
  const currentIndex = visibleItems.findIndex(
    (item) => item.job.key === reviewedKey,
  );
  const visibleRemaining = visibleItems.filter(
    (item) => item.job.key !== reviewedKey,
  );
  if (currentIndex < 0) return visibleRemaining[0] ?? null;
  return (
    visibleRemaining[currentIndex] ?? visibleRemaining[currentIndex - 1] ?? null
  );
}
