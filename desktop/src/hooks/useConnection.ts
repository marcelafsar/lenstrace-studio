import { useEffect, useState } from 'react';
import { api, setConnection } from '@/services/api';

type Status = 'connecting' | 'ready' | 'error';

/** Establish the backend connection (host/port/token) and verify /health. */
export function useConnection(): { status: Status; error: string | null } {
  const [status, setStatus] = useState<Status>('connecting');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (!window.lenstrace) {
          throw new Error('Desktop bridge unavailable (run via run_desktop.py).');
        }
        const conn = await window.lenstrace.getConnection();
        if (!conn || !conn.port || !conn.token) {
          throw new Error(
            'The desktop app did not receive a valid backend connection ' +
              '(missing port or session token). Make sure the app was started ' +
              'with "python run_desktop.py".'
          );
        }
        setConnection(conn);
        await api.health();
        if (!cancelled) setStatus('ready');
      } catch (e) {
        // Surfaced in the renderer console so it's visible in DevTools and,
        // when LENSTRACE_DEBUG is set, forwarded to the launcher's terminal.
        // eslint-disable-next-line no-console
        console.error('[lenstrace] backend connection failed:', e);
        if (!cancelled) {
          setError(String(e));
          setStatus('error');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { status, error };
}
