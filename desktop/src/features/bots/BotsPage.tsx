import { useEffect, useState } from 'react';
import { Banner } from '@/components/Banner';
import { ApiError } from '@/services/api';
import { BotCard } from './BotCard';
import { botsApi } from './bots.api';
import type { BotView } from './bots.types';

export function BotsPage() {
  const [bots, setBots] = useState<BotView[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    botsApi
      .list()
      .then((r) => !cancelled && setBots(r.bots))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="content-inner">
      <h1 className="page-title">Bots</h1>
      <p className="page-sub">
        Set up and control the Telegram and Discord bots. Tokens are stored securely and never shown
        again after saving.
      </p>

      <Banner kind="info">
        Bots run as separate local processes. They never start automatically unless you enable
        auto-start, and they stop when LensTrace closes.
      </Banner>

      {error && <Banner kind="error">{error}</Banner>}
      {!bots && <p className="hint">Loading bots…</p>}

      {bots && (
        <div className="bot-grid">
          {bots.map((b) => (
            <BotCard key={b.kind} initial={b} />
          ))}
        </div>
      )}
    </div>
  );
}
