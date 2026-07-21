import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import { BackendManager } from './backendManager';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// In dev, run_desktop.py starts the backend and passes these via env.
// In a packaged build, BackendManager launches the bundled backend executable.
const DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL;
const isDev = !!DEV_SERVER_URL;
// Opt-in only: keeps DevTools from popping open on every dev launch.
const DEBUG = /^(1|true)$/i.test(process.env.LENSTRACE_DEBUG ?? '');

interface BackendConnection {
  host: string;
  port: number;
  token: string;
}

function redactToken(token: string): string {
  if (!token) return '<empty>';
  return token.length <= 8 ? '<redacted>' : `${token.slice(0, 4)}…<redacted, ${token.length} chars>`;
}

function log(...args: unknown[]): void {
  // eslint-disable-next-line no-console
  console.log('[lenstrace:main]', ...args);
}

function logError(...args: unknown[]): void {
  // eslint-disable-next-line no-console
  console.error('[lenstrace:main]', ...args);
}

let mainWindow: BrowserWindow | null = null;
// Resolved once at startup and served to the renderer on demand via IPC —
// no reliance on cross-world globals or one-shot events that can race with
// the page's own script initialisation.
let connection: BackendConnection | null = null;
const backend = new BackendManager();

async function resolveBackend(): Promise<BackendConnection> {
  if (isDev) {
    const host = process.env.LENSTRACE_BACKEND_HOST || '127.0.0.1';
    const portRaw = process.env.LENSTRACE_BACKEND_PORT;
    const port = Number(portRaw);
    const token = process.env.LENSTRACE_SESSION_TOKEN || '';

    log('Dev mode: reading backend connection from environment', {
      host,
      port: portRaw,
      token: redactToken(token),
    });

    if (!portRaw || !Number.isInteger(port) || port <= 0) {
      throw new Error(
        `LENSTRACE_BACKEND_PORT is missing or invalid (got ${JSON.stringify(portRaw)}). ` +
          'This app must be started with "python run_desktop.py", not "npm run dev" directly.'
      );
    }
    if (!token) {
      throw new Error(
        'LENSTRACE_SESSION_TOKEN is missing. This app must be started with ' +
          '"python run_desktop.py", not "npm run dev" directly.'
      );
    }
    return { host, port, token };
  }
  // Production: spawn the packaged backend and wait for it to report ready.
  log('Production mode: starting bundled backend executable.');
  return backend.start();
}

async function createWindow(): Promise<void> {
  try {
    connection = await resolveBackend();
  } catch (err) {
    logError('Failed to resolve backend connection:', err);
    dialog.showErrorBox(
      'LensTrace Studio — backend unavailable',
      err instanceof Error ? err.message : String(err)
    );
    app.quit();
    return;
  }

  log(
    `Backend connection ready: host=${connection.host} port=${connection.port} ` +
      `token=${redactToken(connection.token)}`
  );

  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 940,
    minHeight: 680,
    backgroundColor: '#12131a',
    titleBarStyle: 'default',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (DEBUG) {
    mainWindow.webContents.on('console-message', (_e, _level, message) => {
      log('[renderer console]', message);
    });
  }

  mainWindow.once('ready-to-show', () => mainWindow?.show());

  if (isDev && DEV_SERVER_URL) {
    await mainWindow.loadURL(DEV_SERVER_URL);
    if (DEBUG) mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    await mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

// The renderer calls this (via preload) once it's ready to receive the
// connection. Since `connection` is resolved before the BrowserWindow is even
// created, there is no timing window in which this can be called too early.
ipcMain.handle('backend:get-connection', () => {
  log('Renderer requested backend connection.');
  return connection;
});

// ---- IPC: native dialogs and file reads (renderer has no Node access) ----

ipcMain.handle('dialog:openImages', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: 'Select images',
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'tiff', 'tif', 'webp', 'heic', 'heif'] }],
  });
  if (result.canceled) return [];
  return result.filePaths.map((p) => ({
    path: p,
    name: path.basename(p),
    bytes: fs.readFileSync(p).toString('base64'),
  }));
});

ipcMain.handle('dialog:chooseOutputDir', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: 'Choose output folder',
    properties: ['openDirectory', 'createDirectory'],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('shell:openPath', async (_e, target: string) => {
  return shell.openPath(target);
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  backend.stop();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => backend.stop());

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
