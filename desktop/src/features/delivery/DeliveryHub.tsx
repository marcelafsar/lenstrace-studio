import { useEffect, useState } from 'react';
import { Banner } from '@/components/Banner';
import { ApiError } from '@/services/api';
import { useExportsStore } from '@/stores/useExportsStore';
import { useNavStore } from '@/stores/useNavStore';
import { DeliveryMethodCard } from './DeliveryMethodCard';
import { deliveryApi } from './delivery.api';
import type { ProvidersResponse } from './delivery.types';

const PROVIDER_ORDER = ['icloud_photos', 'pairdrop', 'apple_devices'] as const;

export function DeliveryHub() {
  const items = useExportsStore((s) => s.items);
  const selectedId = useExportsStore((s) => s.selectedId);
  const select = useExportsStore((s) => s.select);
  const goToSection = useNavStore((s) => s.setSection);

  const [providers, setProviders] = useState<ProvidersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    deliveryApi
      .providers()
      .then((p) => !cancelled && setProviders(p))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = items.find((i) => i.exportId === selectedId) ?? items[0];

  if (items.length === 0) {
    return (
      <div className="content-inner">
        <h1 className="page-title">Send to iPhone</h1>
        <p className="page-sub">Export an image first, then send it to your iPhone from here.</p>
        <Banner kind="info">
          No exports yet in this session. Use the Editor to configure and export an image.
        </Banner>
        <button className="btn primary" onClick={() => goToSection('editor')}>
          Go to Editor
        </button>
      </div>
    );
  }

  return (
    <div className="content-inner">
      <h1 className="page-title">Send to iPhone</h1>
      <p className="page-sub">Move the exact exported file toward your iPhone. Your original is untouched.</p>

      <Banner kind="info">
        LensTrace preserves the exported file and embedded metadata. Apple and external transfer
        services control final import behaviour and source information. Metadata can be edited and
        does not prove when, where, or with which device an image was captured.
      </Banner>

      {error && <Banner kind="error">{error}</Banner>}

      {/* Export selector */}
      {items.length > 1 && (
        <div className="export-strip">
          {items.map((it) => (
            <button
              key={it.exportId}
              className={`export-chip ${it.exportId === selected.exportId ? 'active' : ''}`}
              onClick={() => select(it.exportId)}
              title={it.name}
            >
              {it.thumbnailDataUri && <img src={it.thumbnailDataUri} alt="" />}
              <span>{it.name}</span>
            </button>
          ))}
        </div>
      )}

      <div className="panel export-summary">
        {selected.thumbnailDataUri && (
          <img className="summary-thumb" src={selected.thumbnailDataUri} alt={selected.name} />
        )}
        <div>
          <h3 style={{ margin: '0 0 4px' }}>{selected.name}</h3>
          <p className="hint">Exported this session. Choose a delivery method below.</p>
        </div>
      </div>

      {!providers && <p className="hint">Checking available methods…</p>}

      {providers && (
        <div className="provider-grid">
          {PROVIDER_ORDER.map((pid) => {
            const availability = providers.providers.find((p) => p.provider_id === pid);
            if (!availability) return null;
            return (
              <DeliveryMethodCard
                key={pid}
                availability={availability}
                exportId={selected.exportId}
                defaultPairdropUrl={providers.pairdrop_default_url}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
