import { contextBridge, ipcRenderer } from 'electron';

export interface BackendConnection {
  host: string;
  port: number;
  token: string;
}

export interface PickedFile {
  path: string;
  name: string;
  bytes: string; // base64
}

// A minimal, explicitly-enumerated bridge. The renderer never gets raw Node or
// ipcRenderer access — only these vetted calls.
const api = {
  /**
   * Resolve the local backend connection (host/port/session token).
   *
   * Uses a request/response IPC call rather than a one-shot event: the main
   * process resolves the connection before the window is even created, so
   * invoking this on demand (whenever the renderer is ready) cannot race with
   * a "sent before anyone was listening" event loss.
   */
  getConnection: (): Promise<BackendConnection> => ipcRenderer.invoke('backend:get-connection'),

  openImages: (): Promise<PickedFile[]> => ipcRenderer.invoke('dialog:openImages'),
  chooseOutputDir: (): Promise<string | null> => ipcRenderer.invoke('dialog:chooseOutputDir'),
  openPath: (target: string): Promise<string> => ipcRenderer.invoke('shell:openPath', target),
};

contextBridge.exposeInMainWorld('lenstrace', api);

export type LensTraceApi = typeof api;
