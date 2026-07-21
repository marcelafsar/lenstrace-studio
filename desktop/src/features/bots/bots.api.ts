import { request } from '@/services/api';
import type { BotKind, BotValidation, BotView } from './bots.types';

interface LogsResponse {
  logs: string[];
}

export const botsApi = {
  list: () => request<{ bots: BotView[] }>('/bots'),

  get: (kind: BotKind) => request<BotView>(`/bots/${kind}`),

  validate: (kind: BotKind, token?: string) =>
    request<BotValidation>(`/bots/${kind}/validate`, {
      method: 'POST',
      body: JSON.stringify({ token: token ?? null }),
    }),

  saveToken: (kind: BotKind, token: string) =>
    request<BotView>(`/bots/${kind}/token`, {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),

  clearToken: (kind: BotKind) => request<BotView>(`/bots/${kind}/secret`, { method: 'DELETE' }),

  updateSettings: (
    kind: BotKind,
    settings: { enabled?: boolean; auto_start?: boolean; guild_id?: string | null }
  ) =>
    request<BotView>(`/bots/${kind}/settings`, {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  start: (kind: BotKind) => request<BotView>(`/bots/${kind}/start`, { method: 'POST' }),
  stop: (kind: BotKind) => request<BotView>(`/bots/${kind}/stop`, { method: 'POST' }),
  restart: (kind: BotKind) => request<BotView>(`/bots/${kind}/restart`, { method: 'POST' }),

  logs: (kind: BotKind) => request<LogsResponse>(`/bots/${kind}/logs`),
};
