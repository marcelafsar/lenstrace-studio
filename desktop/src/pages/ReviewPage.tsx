import { useEffect, useState } from 'react';
import { PageNav } from '@/components/PageNav';
import { Banner } from '@/components/Banner';
import { api, ApiError } from '@/services/api';
import { buildChangeRequest } from '@/services/buildRequest';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import type { ChangeDiff } from '@/types';

export function ReviewPage() {
  const files = useWorkflowStore((s) => s.files);
  const activeIndex = useWorkflowStore((s) => s.activeIndex);
  const [diff, setDiff] = useState<ChangeDiff | null>(null);
  const [destName, setDestName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const active = files[activeIndex];

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    setError(null);
    const req = buildChangeRequest(active.file.file_id, useWorkflowStore.getState());
    api
      .preview(req)
      .then((r) => {
        setDiff(r.diff);
        setDestName(r.destination_name);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [active]);

  if (!active) return <Banner kind="warn">No image selected.</Banner>;

  return (
    <div className="content-inner">
      <h1 className="page-title">Review changes</h1>
      <p className="page-sub">
        Confirm what will be written to the exported copy of <strong>{active.file.original_name}</strong>.
        {files.length > 1 && ` These settings apply to all ${files.length} selected images.`}
      </p>

      <Banner kind="info">
        Nothing is written until you export. Metadata does not prove when, where, or how an image
        was captured.
      </Banner>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="panel">
        {loading && <p className="hint">Building preview…</p>}
        {diff && (
          <table className="diff-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Original</th>
                <th>New</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {diff.rows.map((row) => (
                <tr key={row.field}>
                  <td>{row.field}</td>
                  <td style={{ color: 'var(--text-dim)' }}>{row.original ?? '—'}</td>
                  <td>{row.new ?? '—'}</td>
                  <td>
                    <span className={`tag ${row.status}`}>{row.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {diff && (
          <p className="hint" style={{ marginTop: 14 }}>
            Output file: <strong>{destName}</strong>
          </p>
        )}
      </div>

      <PageNav nextLabel="Go to export" nextDisabled={loading || !!error} />
    </div>
  );
}
