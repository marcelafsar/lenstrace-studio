// Address search via OpenStreetMap Nominatim.
//
// Follows Nominatim usage policy: a descriptive User-Agent-style Referer,
// client-side rate limiting (max 1 request/second), and a small result cache.
// Images are NEVER sent — only the typed query string.

export interface GeoResult {
  displayName: string;
  latitude: number;
  longitude: number;
}

const ENDPOINT = 'https://nominatim.openstreetmap.org/search';
const MIN_INTERVAL_MS = 1100;
const cache = new Map<string, GeoResult[]>();
let lastCall = 0;

export async function searchAddress(query: string): Promise<GeoResult[]> {
  const key = query.trim().toLowerCase();
  if (!key) return [];
  if (cache.has(key)) return cache.get(key)!;

  const wait = MIN_INTERVAL_MS - (Date.now() - lastCall);
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastCall = Date.now();

  const url = `${ENDPOINT}?q=${encodeURIComponent(query)}&format=jsonv2&limit=5`;
  const resp = await fetch(url, {
    headers: {
      // Browsers control User-Agent; Referer identifies the app per policy.
      'Accept-Language': 'en',
    },
  });
  if (!resp.ok) throw new Error(`Address search failed (${resp.status})`);
  const data = (await resp.json()) as Array<{ display_name: string; lat: string; lon: string }>;
  const results = data.map((d) => ({
    displayName: d.display_name,
    latitude: Number(d.lat),
    longitude: Number(d.lon),
  }));
  cache.set(key, results);
  return results;
}
