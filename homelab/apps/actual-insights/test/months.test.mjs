// Month-boundary tests use the configured operator time zone, not container UTC.
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  currentMonthInTimeZone,
  previousCompletedMonth,
} from '../src/months.mjs';

test('uses the operator month near a UTC boundary', () => {
  const boundary = new Date('2026-07-31T14:45:00Z');
  assert.equal(currentMonthInTimeZone('Australia/Adelaide', boundary), '2026-08');
  assert.equal(previousCompletedMonth('Australia/Adelaide', boundary), '2026-07');
  assert.equal(previousCompletedMonth('Etc/UTC', boundary), '2026-06');
});
