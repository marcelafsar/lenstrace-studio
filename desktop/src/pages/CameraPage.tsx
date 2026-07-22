import { useEffect, useMemo, useState } from 'react';
import { Banner } from '@/components/Banner';
import { PageNav } from '@/components/PageNav';
import { api, ApiError } from '@/services/api';
import { buildChangeRequest } from '@/services/buildRequest';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import type {
  CameraPreview,
  ExposureMode,
  ExposureProfile,
  ResolutionMode,
} from '@/types';

const EXPOSURE_MODES: { value: ExposureMode; label: string }[] = [
  { value: 'preserve', label: 'Preserve existing' },
  { value: 'fill_missing', label: 'Fill missing fields' },
  { value: 'override', label: 'Override with profile' },
  { value: 'custom', label: 'Custom values' },
];

const RESOLUTION_MODES: { value: ResolutionMode; label: string }[] = [
  { value: 'keep', label: 'Keep original' },
  { value: 'iphone_12mp', label: 'iPhone-style 12 MP' },
  { value: 'custom', label: 'Custom' },
];

export function CameraPage() {
  const files = useWorkflowStore((s) => s.files);
  const activeIndex = useWorkflowStore((s) => s.activeIndex);
  const exposure = useWorkflowStore((s) => s.exposure);
  const resolution = useWorkflowStore((s) => s.resolution);
  const setExposure = useWorkflowStore((s) => s.setExposure);
  const setResolution = useWorkflowStore((s) => s.setResolution);

  const [profiles, setProfiles] = useState<ExposureProfile[]>([]);
  const [preview, setPreview] = useState<CameraPreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const active = files[activeIndex];
  const usesProfile = exposure.mode === 'fill_missing' || exposure.mode === 'override';

  useEffect(() => {
    api
      .getExposureProfiles()
      .then((r) => setProfiles(r.profiles))
      .catch(() => setProfiles([]));
  }, []);

  // The live summary is generated from the actual change plan (never hardcoded).
  useEffect(() => {
    if (!active) return;
    const req = buildChangeRequest(active.file.file_id, useWorkflowStore.getState());
    const timer = setTimeout(() => {
      api
        .preview(req)
        .then((r) => {
          setPreview(r.camera_preview ?? null);
          setError(null);
        })
        .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
    }, 150);
    return () => clearTimeout(timer);
  }, [active, exposure, resolution]);

  const resolutionChanges = useMemo(
    () => resolution.mode !== 'keep',
    [resolution.mode]
  );

  if (!active) return <Banner kind="warn">No image selected.</Banner>;

  return (
    <div className="content-inner">
      <h1 className="page-title">Camera exposure &amp; resolution</h1>
      <p className="page-sub">
        Generated exposure values are <strong>simulated metadata</strong> — not measurements from
        the actual capture. The lens preset supplies aperture and 35&nbsp;mm focal length.
      </p>

      {error && <Banner kind="error">{error}</Banner>}

      {/* ---- Camera Exposure ---- */}
      <div className="panel">
        <h4 style={{ marginTop: 0 }}>Camera Exposure</h4>
        <div className="segmented">
          {EXPOSURE_MODES.map((m) => (
            <button
              key={m.value}
              className={exposure.mode === m.value ? 'on' : ''}
              onClick={() => setExposure({ mode: m.value })}
            >
              {m.label}
            </button>
          ))}
        </div>

        {usesProfile && (
          <div style={{ marginTop: 12 }}>
            <label className="field">
              <span>Simulation profile</span>
              <select
                value={exposure.profileId}
                onChange={(e) => setExposure({ profileId: e.target.value })}
              >
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name} — ISO {p.iso}, {p.exposure_time}s
                    {p.flash_fired ? ', flash' : ''}
                  </option>
                ))}
              </select>
            </label>
            <p className="hint">Simulated exposure metadata ({exposure.profileId} profile).</p>
          </div>
        )}

        {exposure.mode === 'custom' && (
          <div className="grid-2" style={{ marginTop: 12 }}>
            <label className="field">
              <span>ISO</span>
              <input
                type="number"
                value={exposure.iso}
                placeholder="200"
                onChange={(e) => setExposure({ iso: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Shutter (e.g. 1/500)</span>
              <input
                type="text"
                value={exposure.shutter}
                placeholder="1/500"
                onChange={(e) => setExposure({ shutter: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Exposure compensation (EV)</span>
              <input
                type="number"
                step="0.1"
                value={exposure.ev}
                onChange={(e) => setExposure({ ev: e.target.value })}
              />
            </label>
            <label className="field" style={{ alignSelf: 'end' }}>
              <span>
                <input
                  type="checkbox"
                  checked={exposure.flashFired}
                  onChange={(e) => setExposure({ flashFired: e.target.checked })}
                />{' '}
                Flash fired
              </span>
            </label>
          </div>
        )}

        {exposure.mode === 'preserve' && (
          <label className="field" style={{ marginTop: 12 }}>
            <span>
              <input
                type="checkbox"
                checked={exposure.autoFill}
                onChange={(e) => setExposure({ autoFill: e.target.checked })}
              />{' '}
              Auto-fill missing camera exposure fields (iPhone presets)
            </span>
          </label>
        )}
      </div>

      {/* ---- Output Resolution ---- */}
      <div className="panel">
        <h4 style={{ marginTop: 0 }}>Output Resolution</h4>
        <div className="segmented">
          {RESOLUTION_MODES.map((m) => (
            <button
              key={m.value}
              className={resolution.mode === m.value ? 'on' : ''}
              onClick={() => setResolution({ mode: m.value })}
            >
              {m.label}
            </button>
          ))}
        </div>

        {resolution.mode === 'iphone_12mp' && (
          <div className="segmented" style={{ marginTop: 12 }}>
            <button
              className={resolution.fit === 'crop_to_fill' ? 'on' : ''}
              onClick={() => setResolution({ fit: 'crop_to_fill' })}
            >
              Crop to fill
            </button>
            <button
              className={resolution.fit === 'fit_with_padding' ? 'on' : ''}
              onClick={() => setResolution({ fit: 'fit_with_padding' })}
            >
              Fit with padding
            </button>
          </div>
        )}

        {resolution.mode === 'custom' && (
          <div className="grid-2" style={{ marginTop: 12 }}>
            <label className="field">
              <span>Width (px)</span>
              <input
                type="number"
                value={resolution.customWidth}
                placeholder="3024"
                onChange={(e) => setResolution({ customWidth: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Height (px)</span>
              <input
                type="number"
                value={resolution.customHeight}
                placeholder="4032"
                onChange={(e) => setResolution({ customHeight: e.target.value })}
              />
            </label>
          </div>
        )}

        {resolutionChanges && (
          <Banner kind="warn">
            This changes the image’s pixel dimensions. It does not restore real detail that was
            absent from the source.
          </Banner>
        )}
      </div>

      {/* ---- Live summary (from the change plan) ---- */}
      {preview && preview.lines.length > 0 && (
        <div className="panel">
          <h4 style={{ marginTop: 0 }}>Live summary</h4>
          <pre className="summary-block">{preview.lines.join('\n')}</pre>
          {preview.exposure_source_label && (
            <p className="hint">{preview.exposure_source_label}</p>
          )}
        </div>
      )}

      <PageNav nextLabel="Date & time" />
    </div>
  );
}
