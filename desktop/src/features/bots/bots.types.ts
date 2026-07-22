// Types mirroring backend/api/routes_bots.py.

export type BotKind = 'telegram' | 'discord';

export type BotRuntimeState =
  | 'not_configured'
  | 'configuration_incomplete'
  | 'ready'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'stopped'
  | 'authentication_failed'
  | 'connection_failed'
  | 'crashed'
  | 'disabled';

export type ConfigSource =
  | 'environment'
  | 'credential-store'
  | 'file'
  | 'dotenv'
  | 'default'
  | 'none';

export interface BotIdentity {
  username?: string | null;
  display_name?: string | null;
  bot_id?: string | null;
}

export interface BotRuntimeStatus {
  state: BotRuntimeState;
  configured: boolean;
  last_started_at?: string | null;
  uptime_seconds?: number | null;
  last_connection_at?: string | null;
  last_error?: string | null;
  restart_count: number;
  pid?: number | null;
  recent_logs: string[];
  // Real-readiness signals reported by the bot process.
  phase?: string | null;
  authenticated?: boolean;
  ready?: boolean;
  commands_synced?: boolean;
  commands_count?: number | null;
  last_processed?: string | null;
  last_handler_error?: string | null;
}

export interface BotView {
  kind: BotKind;
  enabled: boolean;
  auto_start: boolean;
  guild_id?: string | null;
  token_configured: boolean;
  token_source: ConfigSource;
  token_masked_suffix?: string | null;
  identity?: BotIdentity | null;
  runtime: BotRuntimeStatus;
}

export interface BotValidation {
  valid: boolean;
  identity?: BotIdentity | null;
  error?: string | null;
}
