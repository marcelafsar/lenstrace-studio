import { useMemo } from 'react';
import { PageNav } from '@/components/PageNav';
import { Banner } from '@/components/Banner';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { listTimeZones, offsetForZone } from '@/services/timezones';

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

function nowStamp(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// Split/join "YYYY-MM-DD HH:MM:SS" into the two native input values.
function splitStamp(stamp: string): { date: string; time: string } {
  const [date = '', time = ''] = stamp.split(' ');
  return { date, time };
}

export function DateTimePage() {
  const dt = useWorkflowStore((s) => s.dateTime);
  const setDateTime = useWorkflowStore((s) => s.setDateTime);
  const zones = useMemo(() => listTimeZones(), []);
  const { date, time } = splitStamp(dt.datetime);

  const valid = dt.mode === 'keep' || /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(dt.datetime);

  const updateZone = (tz: string) => {
    setDateTime({ timezone: tz, utcOffset: offsetForZone(tz) });
  };

  const updateDate = (d: string) => setDateTime({ datetime: `${d} ${time || '00:00:00'}` });
  const updateTime = (t: string) => {
    const withSeconds = t.length === 5 ? `${t}:00` : t;
    setDateTime({ datetime: `${date || '2020-01-01'} ${withSeconds}` });
  };

  return (
    <div className="content-inner">
      <h1 className="page-title">Date &amp; time</h1>
      <p className="page-sub">Choose whether to keep the original capture time or set a new one.</p>

      <div className="panel">
        <div className="segmented" style={{ marginBottom: 18 }}>
          <button className={dt.mode === 'keep' ? 'on' : ''} onClick={() => setDateTime({ mode: 'keep' })}>
            Keep original
          </button>
          <button className={dt.mode === 'set' ? 'on' : ''} onClick={() => setDateTime({ mode: 'set' })}>
            Set date &amp; time
          </button>
        </div>

        {dt.mode === 'set' && (
          <>
            <div className="inline-fields">
              <label className="field">
                <span>Date</span>
                <input type="date" value={date} onChange={(e) => updateDate(e.target.value)} />
              </label>
              <label className="field">
                <span>Time (24h, with seconds)</span>
                <input type="time" step={1} value={time} onChange={(e) => updateTime(e.target.value)} />
              </label>
            </div>

            <div className="btn-row" style={{ marginTop: 0 }}>
              <button className="btn ghost" onClick={() => setDateTime({ datetime: nowStamp() })}>
                Use current date &amp; time
              </button>
            </div>

            <label className="field" style={{ marginTop: 18 }}>
              <span>Time zone (IANA)</span>
              <input
                list="tz-list"
                value={dt.timezone}
                onChange={(e) => updateZone(e.target.value)}
                placeholder="Search e.g. Europe/Istanbul"
              />
              <datalist id="tz-list">
                {zones.map((z) => (
                  <option key={z} value={z} />
                ))}
              </datalist>
              <p className="hint">
                UTC offset preview: <strong>{dt.utcOffset}</strong> (written to OffsetTime tags)
              </p>
            </label>

            {!valid && <Banner kind="warn">Enter a complete, valid date and time.</Banner>}
          </>
        )}

        {dt.mode === 'keep' && (
          <p className="hint">The existing capture date/time in each image will be left unchanged.</p>
        )}
      </div>

      <PageNav nextLabel="Location" nextDisabled={!valid} />
    </div>
  );
}
