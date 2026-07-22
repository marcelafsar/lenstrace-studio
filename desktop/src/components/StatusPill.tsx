type Tone = 'ok' | 'warn' | 'bad' | 'idle' | 'busy';

const TONE_CLASS: Record<Tone, string> = {
  ok: 'added',
  warn: 'changed',
  bad: 'removed',
  idle: 'preserved',
  busy: 'verified',
};

export function StatusPill({ label, tone }: { label: string; tone: Tone }) {
  return <span className={`tag ${TONE_CLASS[tone]}`}>{label}</span>;
}
