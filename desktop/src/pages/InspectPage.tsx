import { useEffect, useState } from 'react';
import { Banner } from '@/components/Banner';
import { PageNav } from '@/components/PageNav';
import { api } from '@/services/api';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import type { MetadataSummary } from '@/types';

function SummaryTable({ summary }: { summary: MetadataSummary }) {
  const rows: [string, string | number | null | undefined][] = [
    ['Format', summary.image_format],
    ['Dimensions', summary.width && summary.height ? `${summary.width} × ${summary.height}` : '—'],
    ['Make', summary.make ?? '—'],
    ['Model', summary.model ?? '—'],
    ['Lens', summary.lens_model ?? '—'],
    ['Software', summary.software ?? '—'],
    ['Date taken', summary.datetime_original ?? '—'],
    ['UTC offset', summary.offset_time_original ?? '—'],
    [
      'GPS',
      summary.has_gps && summary.gps_latitude != null
        ? `${summary.gps_latitude.toFixed(5)}, ${summary.gps_longitude?.toFixed(5)}`
        : 'None',
    ],
  ];
  return (
    <table className="meta-table">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <td>{k}</td>
            <td>{v ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function InspectPage() {
  const files = useWorkflowStore((s) => s.files);
  const activeIndex = useWorkflowStore((s) => s.activeIndex);
  const setSummary = useWorkflowStore((s) => s.setSummary);
  const [showRaw, setShowRaw] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const active = files[activeIndex];

  useEffect(() => {
    let cancelled = false;
    files.forEach((f) => {
      if (!f.summary) {
        api
          .inspect(f.file.file_id)
          .then((r) => !cancelled && setSummary(f.file.file_id, r.summary))
          .catch((e) => !cancelled && setError(String(e)));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [files, setSummary]);

  if (!active) return <Banner kind="warn">No image selected.</Banner>;

  return (
    <div className="content-inner">
      <h1 className="page-title">Original metadata</h1>
      <p className="page-sub">
        This is the metadata currently stored in <strong>{active.file.original_name}</strong>.
      </p>

      <Banner kind="info">
        Metadata is editable and does not prove when, where, or how a photo was actually captured.
      </Banner>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="panel">
        {active.summary ? <SummaryTable summary={active.summary} /> : <p className="hint">Reading…</p>}
      </div>

      {active.summary && Object.keys(active.summary.raw_tags).length > 0 && (
        <div className="panel">
          <button className="btn ghost" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? 'Hide' : 'Show'} all raw tags ({Object.keys(active.summary.raw_tags).length})
          </button>
          {showRaw && (
            <table className="meta-table" style={{ marginTop: 12 }}>
              <tbody>
                {Object.entries(active.summary.raw_tags).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <PageNav nextLabel="Choose device" />
    </div>
  );
}
