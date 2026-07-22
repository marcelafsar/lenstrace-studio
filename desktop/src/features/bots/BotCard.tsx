import { useEffect, useRef, useState } from 'react';
import { Banner } from '@/components/Banner';
import { StatusPill } from '@/components/StatusPill';
import { ApiError } from '@/services/api';
import { botsApi } from './bots.api';
import type { BotKind, BotRuntimeState, BotValidation, BotView } from './bots.types';

const SETUP_URL: Record<BotKind, string> = {
  telegram: 'https://t.me/BotFather',
  discord: 'https://discord.com/developers/applications',
};

const CHECKLIST: Record<BotKind, string> = {
  telegram:
    'Telegram bot setup:\n1. Open @BotFather in Telegram\n2. Send /newbot and follow prompts\n3. Copy the token BotFather gives you\n4. Paste it here, test, and save',
  discord:
    'Discord bot setup:\n1. Open the Discord Developer Portal\n2. New Application -> Bot -> Reset Token\n3. Copy the bot token\n4. Invite the bot with the applications.commands scope\n5. Paste the token here, test, and save',
};

function pill(state: BotRuntimeState) {
  switch (state) {
    case 'running':
      return <StatusPill label="Running" tone="ok" />;
    case 'starting':
      return <StatusPill label="Starting…" tone="busy" />;
    case 'stopping':
      return <StatusPill label="Stopping…" tone="busy" />;
    case 'stopped':
    case 'ready':
      return <StatusPill label="Stopped" tone="idle" />;
    case 'crashed':
      return <StatusPill label="Crashed" tone="bad" />;
    case 'authentication_failed':
      return <StatusPill label="Auth failed" tone="bad" />;
    case 'connection_failed':
      return <StatusPill label="Connection failed" tone="bad" />;
    default:
      return <StatusPill label="Not configured" tone="idle" />;
  }
}

export function BotCard({ initial }: { initial: BotView }) {
  const kind = initial.kind;
  const [view, setView] = useState<BotView>(initial);
  const [token, setToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [guildId, setGuildId] = useState(initial.guild_id ?? '');
  const [validation, setValidation] = useState<BotValidation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const pollRef = useRef<number | null>(null);

  const running = view.runtime.state === 'running' || view.runtime.state === 'starting';

  // Poll runtime status while the bot is active so state/logs stay fresh.
  useEffect(() => {
    if (!running) {
      if (pollRef.current) window.clearInterval(pollRef.current);
      return;
    }
    pollRef.current = window.setInterval(async () => {
      try {
        setView(await botsApi.get(kind));
      } catch {
        /* transient */
      }
    }, 2500);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [running, kind]);

  const run = async (fn: () => Promise<BotView>) => {
    setBusy(true);
    setError(null);
    try {
      setView(await fn());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const testToken = async () => {
    setBusy(true);
    setError(null);
    try {
      setValidation(await botsApi.validate(kind, token || undefined));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveToken = async () => {
    if (!token.trim()) return;
    await run(async () => {
      if (kind === 'discord' && guildId.trim()) {
        await botsApi.updateSettings(kind, { guild_id: guildId.trim() });
      }
      const v = await botsApi.saveToken(kind, token);
      setToken(''); // clear the input immediately after saving
      setValidation(null);
      return v;
    });
  };

  const clearToken = async () => {
    if (!window.confirm(`Delete the stored ${kind} bot token? The bot will be stopped.`)) return;
    await run(() => botsApi.clearToken(kind));
  };

  const stopBot = async () => {
    if (!window.confirm(`Stop the ${kind} bot?`)) return;
    await run(() => botsApi.stop(kind));
  };

  const copyChecklist = () => navigator.clipboard?.writeText(CHECKLIST[kind]);

  const identity = view.identity ?? validation?.identity;

  return (
    <div className="bot-card">
      <div className="provider-head">
        <div>
          <h3 style={{ margin: 0 }}>{kind === 'telegram' ? 'Telegram Bot' : 'Discord Bot'}</h3>
          {identity?.username && <p className="hint">@{identity.username}</p>}
          {view.token_configured && view.token_masked_suffix && (
            <p className="hint">Token saved ({view.token_masked_suffix}), source: {view.token_source}</p>
          )}
        </div>
        {pill(view.runtime.state)}
      </div>

      {error && <Banner kind="error">{error}</Banner>}
      {view.runtime.last_error && view.runtime.state === 'crashed' && (
        <Banner kind="warn">{view.runtime.last_error}</Banner>
      )}
      {view.runtime.last_handler_error && (
        <Banner kind="warn">Last handler error: {view.runtime.last_handler_error}</Banner>
      )}

      {running && (
        <div className="readiness">
          <ReadyDot on={view.runtime.authenticated} label="Authenticated" />
          {kind === 'telegram' && <ReadyDot on={view.runtime.ready} label="Polling ready" />}
          {kind === 'discord' && (
            <>
              <ReadyDot on={view.runtime.ready} label="Gateway ready" />
              <ReadyDot
                on={view.runtime.commands_synced}
                label={
                  view.runtime.commands_synced && view.runtime.commands_count != null
                    ? `Commands synced (${view.runtime.commands_count})`
                    : 'Commands synced'
                }
              />
            </>
          )}
          {view.runtime.last_processed && (
            <span className="hint">Last: {view.runtime.last_processed}</span>
          )}
        </div>
      )}

      {!view.token_configured && (
        <div className="setup-block">
          <label className="field">
            <span>Bot token</span>
            <div className="inline-fields">
              <input
                type={showToken ? 'text' : 'password'}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste the bot token"
                spellCheck={false}
                autoComplete="off"
              />
              <button className="btn ghost" style={{ flex: 'none' }} onClick={() => setShowToken((v) => !v)}>
                {showToken ? 'Hide' : 'Show'}
              </button>
            </div>
          </label>
          {kind === 'discord' && (
            <label className="field">
              <span>Development guild ID (optional)</span>
              <input value={guildId} onChange={(e) => setGuildId(e.target.value)} spellCheck={false} />
            </label>
          )}
          {validation && (
            <Banner kind={validation.valid ? 'success' : 'error'}>
              {validation.valid
                ? `Token valid${validation.identity?.username ? ` — @${validation.identity.username}` : ''}.`
                : validation.error}
            </Banner>
          )}
          <div className="btn-row" style={{ marginTop: 4 }}>
            <button className="btn ghost" onClick={() => openUrl(SETUP_URL[kind])}>
              Open setup
            </button>
            <button className="btn ghost" onClick={copyChecklist}>
              Copy checklist
            </button>
            <span className="spacer" />
            <button className="btn" onClick={testToken} disabled={busy || !token.trim()}>
              Test token
            </button>
            <button className="btn primary" onClick={saveToken} disabled={busy || !token.trim()}>
              Save
            </button>
          </div>
        </div>
      )}

      {view.token_configured && (
        <div className="controls-block">
          <div className="btn-row" style={{ marginTop: 0 }}>
            {!running ? (
              <button className="btn primary" onClick={() => run(() => botsApi.start(kind))} disabled={busy}>
                Start
              </button>
            ) : (
              <button className="btn" onClick={stopBot} disabled={busy}>
                Stop
              </button>
            )}
            <button className="btn ghost" onClick={() => run(() => botsApi.restart(kind))} disabled={busy || !running}>
              Restart
            </button>
            {kind === 'discord' && (
              <button
                className="btn ghost"
                onClick={() => run(() => botsApi.resync(kind))}
                disabled={busy || !running}
                title="Restart the bot to re-sync slash commands"
              >
                Resync commands
              </button>
            )}
            {kind === 'telegram' && identity?.username && (
              <button
                className="btn ghost"
                onClick={() => openUrl(`https://t.me/${identity.username}`)}
              >
                Open bot chat
              </button>
            )}
            <button className="btn ghost" onClick={() => setShowLogs((v) => !v)}>
              {showLogs ? 'Hide logs' : 'View logs'}
            </button>
            <span className="spacer" />
            <button className="btn danger" onClick={clearToken} disabled={busy}>
              Clear token
            </button>
          </div>

          <label className="toggle-row">
            <input
              type="checkbox"
              checked={view.auto_start}
              onChange={(e) => run(() => botsApi.updateSettings(kind, { auto_start: e.target.checked }))}
            />
            <span>Start automatically when LensTrace opens</span>
          </label>

          {view.runtime.uptime_seconds != null && running && (
            <p className="hint">Uptime: {Math.round(view.runtime.uptime_seconds)}s</p>
          )}

          {showLogs && (
            <pre className="log-view">
              {view.runtime.recent_logs.length
                ? view.runtime.recent_logs.join('\n')
                : 'No logs yet.'}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function openUrl(url: string) {
  window.lenstrace?.openExternal(url);
}

function ReadyDot({ on, label }: { on?: boolean; label: string }) {
  return (
    <span className={`ready-dot ${on ? 'on' : ''}`}>
      <span className="dot-mark" aria-hidden>
        {on ? '●' : '○'}
      </span>
      {label}
    </span>
  );
}
