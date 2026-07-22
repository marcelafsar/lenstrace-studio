import { useCallback, useEffect, useState } from 'react';
import { Banner } from '@/components/Banner';
import { StatusPill } from '@/components/StatusPill';
import { ApiError } from '@/services/api';
import { diagnosticsApi } from './diagnostics.api';
import type { CheckReport, CheckResult } from './diagnostics.api';

function pill(status: CheckResult['status']) {
  if (status === 'PASS') return <StatusPill label="PASS" tone="ok" />;
  if (status === 'WARN') return <StatusPill label="WARN" tone="warn" />;
  return <StatusPill label="FAIL" tone="bad" />;
}

const CATEGORY_LABELS: Record<string, string> = {
  core: 'Core desktop',
  general: 'General configuration',
  telegram: 'Telegram',
  discord: 'Discord',
  delivery: 'Delivery methods',
};

export function DiagnosticsPage() {
  const [report, setReport] = useState<CheckReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectivity, setConnectivity] = useState(false);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const load = useCallback(
    async (recheck: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const r = recheck
          ? await diagnosticsApi.recheck(connectivity)
          : await diagnosticsApi.status(connectivity);
        setReport(r.report);
        setCheckedAt(new Date().toLocaleTimeString());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [connectivity]
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  const grouped = (report?.results ?? []).reduce<Record<string, CheckResult[]>>((acc, r) => {
    (acc[r.category] ??= []).push(r);
    return acc;
  }, {});

  const copyReport = () => {
    if (!report) return;
    const text = report.results
      .map((r) => `[${r.status}] ${r.name}${r.detail ? ` - ${r.detail}` : ''}`)
      .join('\n');
    navigator.clipboard?.writeText(text);
  };

  return (
    <div className="content-inner">
      <h1 className="page-title">Diagnostics</h1>
      <p className="page-sub">
        Environment and configuration status. This report contains no secret values.
      </p>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="btn-row" style={{ marginTop: 0 }}>
        <label className="toggle-row" style={{ margin: 0 }}>
          <input
            type="checkbox"
            checked={connectivity}
            onChange={(e) => setConnectivity(e.target.checked)}
          />
          <span>Also test bot tokens over the network</span>
        </label>
        <span className="spacer" />
        {checkedAt && <span className="hint">Last checked {checkedAt}</span>}
        <button className="btn ghost" onClick={copyReport} disabled={!report}>
          Copy report
        </button>
        <button className="btn primary" onClick={() => load(true)} disabled={loading}>
          {loading ? 'Checking…' : 'Recheck'}
        </button>
      </div>

      {report && (
        <p className="hint" style={{ marginTop: 10 }}>
          {report.passed} passed · {report.warned} warnings · {report.failed} failed
        </p>
      )}

      {Object.entries(grouped).map(([category, results]) => (
        <div className="panel" key={category}>
          <h3 style={{ marginTop: 0 }}>{CATEGORY_LABELS[category] ?? category}</h3>
          <table className="meta-table">
            <tbody>
              {results.map((r) => (
                <tr key={r.name}>
                  <td style={{ width: 60 }}>{pill(r.status)}</td>
                  <td>
                    <strong>{r.name}</strong>
                    {r.detail && <div className="hint">{r.detail}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
