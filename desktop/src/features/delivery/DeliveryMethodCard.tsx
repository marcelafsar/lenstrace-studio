import { useState } from 'react';
import { Banner } from '@/components/Banner';
import { QrCode } from '@/components/QrCode';
import { StatusPill } from '@/components/StatusPill';
import { ApiError } from '@/services/api';
import { deliveryApi } from './delivery.api';
import type {
  DeliveryAvailability,
  DeliveryJobStatus,
  DeliveryOptions,
  ProviderPreparation,
} from './delivery.types';

const TITLES: Record<string, string> = {
  icloud_photos: 'iCloud Photos',
  pairdrop: 'PairDrop',
  apple_devices: 'Apple Devices',
};

const SUBTITLES: Record<string, string> = {
  icloud_photos: 'Copy into the iCloud Photos folder. Apple controls sync.',
  pairdrop: 'Browser-based transfer. iOS performs the final save.',
  apple_devices: 'USB/Wi-Fi assisted sync via the Apple Devices app.',
};

function availabilityPill(a: DeliveryAvailability) {
  if (a.level === 'ready') return <StatusPill label="Ready" tone="ok" />;
  if (a.level === 'needs_setup') return <StatusPill label="Needs setup" tone="warn" />;
  return <StatusPill label="Unavailable" tone="bad" />;
}

function statePill(state: DeliveryJobStatus['state']) {
  switch (state) {
    case 'completed':
      return <StatusPill label="Completed" tone="ok" />;
    case 'waiting_for_sync':
      return <StatusPill label="Copied — waiting for sync" tone="ok" />;
    case 'awaiting_user':
      return <StatusPill label="Waiting for you" tone="warn" />;
    case 'copying':
    case 'verifying':
    case 'preparing':
      return <StatusPill label="Working…" tone="busy" />;
    case 'failed':
      return <StatusPill label="Failed" tone="bad" />;
    case 'cancelled':
      return <StatusPill label="Cancelled" tone="idle" />;
    default:
      return <StatusPill label={state} tone="idle" />;
  }
}

interface Props {
  availability: DeliveryAvailability;
  exportId: string;
  defaultPairdropUrl: string;
}

export function DeliveryMethodCard({ availability, exportId, defaultPairdropUrl }: Props) {
  const provider = availability.provider_id;
  const [prep, setPrep] = useState<ProviderPreparation | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<DeliveryJobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chosenFolder, setChosenFolder] = useState<string | null>(null);
  const [customUrl, setCustomUrl] = useState(defaultPairdropUrl);

  const buildOptions = (): DeliveryOptions => {
    const options: DeliveryOptions = {};
    if (provider !== 'pairdrop' && chosenFolder) options.destination_dir = chosenFolder;
    if (provider === 'pairdrop' && customUrl) options.extra = { pairdrop_url: customUrl };
    return options;
  };

  const doPrepare = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await deliveryApi.prepare(provider, exportId, buildOptions());
      setPrep(res.preparation);
      setJobId(res.job_id);
      setStatus(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const doExecute = async () => {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    try {
      setStatus(await deliveryApi.execute(jobId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const chooseFolder = async () => {
    const dir = await window.lenstrace?.chooseOutputDir();
    if (dir) {
      setChosenFolder(dir);
      setPrep(null); // re-prepare with the new destination
    }
  };

  const openUrl = (url?: string | null) => {
    if (url) window.lenstrace?.openExternal(url);
  };
  const openFolder = () => {
    if (chosenFolder) window.lenstrace?.openPath(chosenFolder);
  };

  const unavailable = availability.level === 'unavailable';

  return (
    <div className={`provider-card ${availability.recommended ? 'recommended' : ''}`}>
      <div className="provider-head">
        <div>
          <h3>
            {TITLES[provider]}{' '}
            {availability.recommended && <span className="tag verified">Recommended</span>}
          </h3>
          <p className="hint">{SUBTITLES[provider]}</p>
        </div>
        {status ? statePill(status.state) : availabilityPill(availability)}
      </div>

      <p className="hint">{availability.summary}</p>

      {error && <Banner kind="error">{error}</Banner>}

      {/* Provider-specific destination controls */}
      {provider !== 'pairdrop' && !status && (
        <div className="btn-row" style={{ marginTop: 8 }}>
          <button className="btn ghost" onClick={chooseFolder} disabled={busy}>
            {chosenFolder ? 'Change folder…' : 'Choose folder…'}
          </button>
          {chosenFolder && <span className="hint">Destination selected.</span>}
        </div>
      )}

      {provider === 'pairdrop' && !status && (
        <label className="field" style={{ marginTop: 8 }}>
          <span>PairDrop instance</span>
          <input
            type="text"
            value={customUrl}
            onChange={(e) => setCustomUrl(e.target.value)}
            spellCheck={false}
          />
        </label>
      )}

      {!prep && !status && (
        <button className="btn primary" onClick={doPrepare} disabled={busy || unavailable}>
          {busy ? 'Preparing…' : 'Prepare'}
        </button>
      )}

      {prep && !status && (
        <div className="prep-block">
          {prep.destination_label && (
            <p className="hint">
              Destination: <strong>{prep.destination_label}</strong>
              {prep.destination_name ? ` / ${prep.destination_name}` : ''}
            </p>
          )}
          {prep.user_action?.open_url && provider === 'pairdrop' && (
            <div className="qr-wrap">
              <QrCode url={prep.user_action.open_url} />
              <p className="hint">Scan on your iPhone (payload is only the PairDrop URL).</p>
            </div>
          )}
          {prep.user_action?.instructions && (
            <ol className="steps">
              {prep.user_action.instructions.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          )}
          {prep.notes.map((note) => (
            <p key={note} className="hint">
              {note}
            </p>
          ))}
          <div className="btn-row" style={{ marginTop: 8 }}>
            {prep.user_action?.open_url && (
              <button className="btn" onClick={() => openUrl(prep.user_action?.open_url)}>
                Open {provider === 'pairdrop' ? 'PairDrop' : 'link'}
              </button>
            )}
            <span className="spacer" />
            <button
              className="btn primary"
              onClick={doExecute}
              disabled={busy || !prep.ready_to_execute}
            >
              {provider === 'pairdrop' ? 'I opened PairDrop' : busy ? 'Copying…' : 'Copy & verify'}
            </button>
          </div>
          {!prep.ready_to_execute && (
            <p className="hint">Choose a destination folder above to continue.</p>
          )}
        </div>
      )}

      {status && (
        <div className="status-block">
          <p>{status.message}</p>
          {status.destination_verified && (
            <Banner kind="success">
              Copy verified by SHA-256 and metadata. {status.destination_name}
            </Banner>
          )}
          {status.warnings.map((w) => (
            <Banner key={w} kind="warn">
              {w}
            </Banner>
          ))}
          {status.user_action?.instructions && status.state === 'awaiting_user' && (
            <ol className="steps">
              {status.user_action.instructions.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          )}
          <div className="btn-row" style={{ marginTop: 8 }}>
            {status.user_action?.open_url && (
              <button className="btn" onClick={() => openUrl(status.user_action?.open_url)}>
                Open again
              </button>
            )}
            {status.user_action?.open_app === 'apple_devices' && (
              <span className="hint">Open the Apple Devices app to finish syncing.</span>
            )}
            {chosenFolder && (
              <button className="btn ghost" onClick={openFolder}>
                Open folder
              </button>
            )}
            <span className="spacer" />
            <button
              className="btn ghost"
              onClick={() => {
                setStatus(null);
                setPrep(null);
              }}
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
