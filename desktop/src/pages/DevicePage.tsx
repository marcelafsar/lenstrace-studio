import { useMemo, useState } from 'react';
import { Banner } from '@/components/Banner';
import { PageNav } from '@/components/PageNav';
import { usePresets } from '@/hooks/usePresets';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import type { Device } from '@/types';

export function DevicePage() {
  const { devices, loading, error } = usePresets();
  const presetId = useWorkflowStore((s) => s.presetId);
  const lensId = useWorkflowStore((s) => s.lensId);
  const setDevice = useWorkflowStore((s) => s.setDevice);
  const [query, setQuery] = useState('');

  const selected: Device | undefined = devices.find((d) => d.id === presetId);

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? devices.filter((d) => d.display_name.toLowerCase().includes(q))
      : devices;
    const groups: Record<string, Device[]> = {};
    for (const d of filtered) {
      const key = d.generation ?? 'Other';
      (groups[key] ??= []).push(d);
    }
    return groups;
  }, [devices, query]);

  if (loading) return <p className="hint">Loading device presets…</p>;
  if (error) return <Banner kind="error">{error}</Banner>;

  return (
    <div className="content-inner">
      <h1 className="page-title">Device &amp; lens</h1>
      <p className="page-sub">
        Choose the camera identity to write. Values come from the versioned preset data.
      </p>

      <div className="panel">
        <label className="field">
          <span>Search devices</span>
          <input
            type="search"
            placeholder="e.g. iPhone 13 Pro"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>

        {Object.entries(grouped).map(([gen, list]) => (
          <div className="device-group" key={gen}>
            <h4>{gen}</h4>
            <div className="device-list">
              {list.map((d) => (
                <button
                  key={d.id}
                  className={`device-chip ${d.id === presetId ? 'selected' : ''}`}
                  onClick={() => setDevice(d.id, d.lenses[0]?.id ?? null)}
                >
                  {d.display_name}{' '}
                  {d.source_status === 'placeholder' && (
                    <span className="tag placeholder" style={{ marginLeft: 4 }}>
                      unverified
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {selected && (
        <div className="panel">
          <h4 style={{ marginTop: 0 }}>Lens</h4>
          <div className="segmented">
            {selected.lenses.map((lens) => (
              <button
                key={lens.id}
                className={lens.id === lensId ? 'on' : ''}
                onClick={() => setDevice(selected.id, lens.id)}
              >
                {lens.display_name}
              </button>
            ))}
          </div>
          <p className="hint" style={{ marginTop: 12 }}>
            Will write Model = <strong>{selected.exif_model}</strong>. Lens EXIF values are only
            written when the preset provides them (friendly names are labels, not written data).
          </p>
          {selected.notes && <p className="hint">{selected.notes}</p>}
          <button
            className="btn ghost"
            style={{ marginTop: 10 }}
            onClick={() => setDevice(null, null)}
          >
            Clear device (keep original)
          </button>
        </div>
      )}

      <PageNav nextLabel="Camera & resolution" />
    </div>
  );
}
