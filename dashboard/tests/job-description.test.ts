import { describe, expect, test } from 'vitest';
import {
  cleanJobDescription,
  jobDescriptionSummary,
} from '../app/job-description';

describe('job description formatting', () => {
  test('removes nested entities and backslash-escaped HTML', () => {
    const description =
      'Lead architecture.&amp;nbsp;\\</p> \\&lt;p&gt;\\&lt;br&gt;Improve delivery &amp;amp; reliability.';

    expect(cleanJobDescription(description)).toBe(
      'Lead architecture.\nImprove delivery & reliability.',
    );
    expect(jobDescriptionSummary(description)).toBe(
      'Lead architecture. Improve delivery & reliability.',
    );
  });

  test('preserves paragraph and list boundaries as readable text', () => {
    const description =
      '<p>Responsibilities</p><ul><li>Build platforms</li><li>Lead delivery</li></ul>';

    expect(cleanJobDescription(description)).toBe(
      'Responsibilities\n• Build platforms\n• Lead delivery',
    );
  });
});
