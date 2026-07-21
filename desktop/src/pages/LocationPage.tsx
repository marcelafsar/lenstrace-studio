import { useState } from 'react';
import { PageNav } from '@/components/PageNav';
import { Banner } from '@/components/Banner';
import { MapPicker } from '@/components/MapPicker';
import { searchAddress, type GeoResult } from '@/services/geocode';
import { useWorkflowStore } from '@/stores/useWorkflowStore';

export function LocationPage() {
  const location = useWorkflowStore((s) => s.location);
  const setLocation = useWorkflowStore((s) => s.setLocation);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeoResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gps = location.gps;

  const setCoords = (lat: number, lon: number) => {
    setLocation({
      mode: 'set',
      gps: {
        latitude: Number(lat.toFixed(6)),
        longitude: Number(lon.toFixed(6)),
        altitude_m: gps?.altitude_m ?? null,
        address_label: gps?.address_label ?? null,
      },
    });
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      setResults(await searchAddress(query));
    } catch (e) {
      setError(String(e));
    } finally {
      setSearching(false);
    }
  };

  const copyCoords = () => {
    if (gps) navigator.clipboard?.writeText(`${gps.latitude}, ${gps.longitude}`);
  };

  return (
    <div className="content-inner">
      <h1 className="page-title">Location</h1>
      <p className="page-sub">Optional. Set GPS by address, map click, or manual coordinates.</p>

      <div className="panel">
        <div className="segmented" style={{ marginBottom: 16 }}>
          <button className={location.mode === 'keep' ? 'on' : ''} onClick={() => setLocation({ mode: 'keep' })}>
            Keep original
          </button>
          <button className={location.mode === 'set' ? 'on' : ''} onClick={() => setLocation({ mode: 'set' })}>
            Set location
          </button>
          <button
            className={location.mode === 'remove' ? 'on' : ''}
            onClick={() => setLocation({ mode: 'remove', gps: null })}
          >
            Remove GPS
          </button>
        </div>

        {location.mode === 'set' && (
          <>
            <label className="field">
              <span>Search for an address (optional)</span>
              <div className="inline-fields">
                <input
                  type="search"
                  value={query}
                  placeholder="e.g. Sultanahmet, Istanbul"
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && runSearch()}
                />
                <button className="btn" style={{ flex: 'none' }} onClick={runSearch} disabled={searching}>
                  {searching ? 'Searching…' : 'Search'}
                </button>
              </div>
            </label>

            {error && <Banner kind="error">{error}</Banner>}
            {results.length > 0 && (
              <div className="device-list" style={{ marginBottom: 14 }}>
                {results.map((r) => (
                  <button
                    key={`${r.latitude},${r.longitude}`}
                    className="device-chip"
                    onClick={() => {
                      setCoords(r.latitude, r.longitude);
                      setLocation({ gps: { latitude: r.latitude, longitude: r.longitude, altitude_m: null, address_label: r.displayName } });
                      setResults([]);
                    }}
                  >
                    {r.displayName}
                  </button>
                ))}
              </div>
            )}

            <MapPicker
              latitude={gps?.latitude ?? null}
              longitude={gps?.longitude ?? null}
              onPick={setCoords}
            />

            <div className="inline-fields" style={{ marginTop: 16 }}>
              <label className="field">
                <span>Latitude</span>
                <input
                  type="number"
                  step="0.000001"
                  value={gps?.latitude ?? ''}
                  onChange={(e) => setCoords(Number(e.target.value), gps?.longitude ?? 0)}
                />
              </label>
              <label className="field">
                <span>Longitude</span>
                <input
                  type="number"
                  step="0.000001"
                  value={gps?.longitude ?? ''}
                  onChange={(e) => setCoords(gps?.latitude ?? 0, Number(e.target.value))}
                />
              </label>
              <label className="field">
                <span>Altitude (m, optional)</span>
                <input
                  type="number"
                  step="0.1"
                  value={gps?.altitude_m ?? ''}
                  onChange={(e) =>
                    setLocation({
                      gps: {
                        latitude: gps?.latitude ?? 0,
                        longitude: gps?.longitude ?? 0,
                        altitude_m: e.target.value === '' ? null : Number(e.target.value),
                        address_label: gps?.address_label ?? null,
                      },
                    })
                  }
                />
              </label>
            </div>

            <div className="btn-row" style={{ marginTop: 0 }}>
              <button className="btn ghost" onClick={copyCoords} disabled={!gps}>
                Copy coordinates
              </button>
              <button className="btn ghost" onClick={() => setLocation({ mode: 'set', gps: null })}>
                Clear
              </button>
            </div>
            <p className="hint">
              Consumer GPS is typically accurate to a few metres. Coordinates you set here are your
              stated values, not a measurement.
            </p>
          </>
        )}

        {location.mode === 'remove' && (
          <Banner kind="warn">Any existing GPS tags will be removed from the exported copy.</Banner>
        )}
        {location.mode === 'keep' && (
          <p className="hint">Existing GPS data (if any) is left unchanged.</p>
        )}
      </div>

      <PageNav nextLabel="Review" />
    </div>
  );
}
