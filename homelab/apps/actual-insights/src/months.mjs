// Supplies month boundaries in the operator's configured IANA time zone.

export function currentMonthInTimeZone(timeZone, date = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
    })
      .formatToParts(date)
      .filter(part => part.type === 'year' || part.type === 'month')
      .map(part => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}`;
}

export function previousCompletedMonth(timeZone, date = new Date()) {
  const [year, month] = currentMonthInTimeZone(timeZone, date).split('-').map(Number);
  return new Date(Date.UTC(year, month - 2, 1)).toISOString().slice(0, 7);
}
