// IANA time-zone helpers for the date/time editor.

export function listTimeZones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (k: string) => string[] };
  if (typeof intl.supportedValuesOf === 'function') {
    try {
      return intl.supportedValuesOf('timeZone');
    } catch {
      /* fall through */
    }
  }
  return [
    'UTC',
    'Europe/London',
    'Europe/Paris',
    'Europe/Istanbul',
    'America/New_York',
    'America/Chicago',
    'America/Los_Angeles',
    'Asia/Tokyo',
    'Asia/Dubai',
    'Australia/Sydney',
  ];
}

/** Compute the "+HH:MM" offset for an IANA zone at a given local wall-clock time. */
export function offsetForZone(timeZone: string, when: Date = new Date()): string {
  try {
    const dtf = new Intl.DateTimeFormat('en-US', {
      timeZone,
      timeZoneName: 'longOffset',
    });
    const part = dtf.formatToParts(when).find((p) => p.type === 'timeZoneName');
    const raw = part?.value ?? 'GMT+00:00';
    const match = raw.match(/GMT([+-]\d{2}:\d{2})/);
    if (match) return match[1];
    if (raw === 'GMT') return '+00:00';
  } catch {
    /* ignore */
  }
  return '+00:00';
}
