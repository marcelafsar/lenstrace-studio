import { useEffect, useState } from 'react';
import { api } from '@/services/api';
import type { Device } from '@/types';

interface PresetsState {
  devices: Device[];
  loading: boolean;
  error: string | null;
}

let cache: Device[] | null = null;

export function usePresets(): PresetsState {
  const [state, setState] = useState<PresetsState>({
    devices: cache ?? [],
    loading: cache === null,
    error: null,
  });

  useEffect(() => {
    if (cache) return;
    let cancelled = false;
    api
      .getPresets()
      .then((r) => {
        cache = r.devices;
        if (!cancelled) setState({ devices: r.devices, loading: false, error: null });
      })
      .catch((e) => {
        if (!cancelled) setState({ devices: [], loading: false, error: String(e) });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
