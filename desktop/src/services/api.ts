// Centralised API client for the local backend. Every request carries the
// session token; all error handling funnels through `request()`.

import type {
  BackendConnection,
  ChangeRequest,
  ExportResponse,
  MetadataSummary,
  PresetsResponse,
  PreviewResponse,
  UploadedFile,
} from '@/types';

export interface InspectResponse {
  file_id: string;
  summary: MetadataSummary;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let connection: BackendConnection | null = null;

export function setConnection(conn: BackendConnection): void {
  connection = conn;
}

function baseUrl(): string {
  if (!connection) throw new ApiError('Backend connection not established', 0);
  return `http://${connection.host}:${connection.port}`;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!connection) throw new ApiError('Backend connection not established', 0);
  const headers = new Headers(init.headers);
  headers.set('X-LensTrace-Token', connection.token);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  let resp: Response;
  try {
    resp = await fetch(`${baseUrl()}${path}`, { ...init, headers });
  } catch (err) {
    throw new ApiError(`Cannot reach the local backend. ${String(err)}`, 0);
  }

  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      detail = body.detail ?? body.error ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  getPresets: () => request<PresetsResponse>('/presets'),

  uploadFile: async (name: string, base64: string): Promise<UploadedFile> => {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const form = new FormData();
    form.append('file', new Blob([bytes]), name);
    return request<UploadedFile>('/files/upload', { method: 'POST', body: form });
  },

  inspect: (fileId: string) => request<InspectResponse>(`/files/${fileId}/inspect`),

  deleteFile: (fileId: string) => request<void>(`/files/${fileId}`, { method: 'DELETE' }),

  preview: (req: ChangeRequest) =>
    request<PreviewResponse>('/metadata/preview', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  export: (req: ChangeRequest) =>
    request<ExportResponse>('/metadata/export', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};
