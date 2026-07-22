import { spawn, ChildProcess } from 'node:child_process';
import net from 'node:net';
import crypto from 'node:crypto';
import path from 'node:path';
import http from 'node:http';
import { app } from 'electron';

export interface BackendConnection {
  host: string;
  port: number;
  token: string;
}

/**
 * Manages the packaged Python backend process in a production build.
 *
 * NOTE: This path is scaffolding for Phase 5. It expects a PyInstaller-built
 * backend executable bundled under resources/backend/. In development the
 * backend is started by run_desktop.py instead, and this class is unused.
 */
export class BackendManager {
  private proc: ChildProcess | null = null;
  private readonly host = '127.0.0.1';

  async start(): Promise<BackendConnection> {
    const port = await this.findFreePort();
    const token = crypto.randomBytes(32).toString('base64url');

    const exeName = process.platform === 'win32' ? 'lenstrace-backend.exe' : 'lenstrace-backend';
    const backendPath = path.join(process.resourcesPath, 'backend', exeName);

    this.proc = spawn(backendPath, [], {
      env: {
        ...process.env,
        LENSTRACE_HOST: this.host,
        LENSTRACE_PORT: String(port),
        LENSTRACE_SESSION_TOKEN: token,
      },
      stdio: 'ignore',
    });

    this.proc.on('exit', (code) => {
      if (code && code !== 0) {
        // eslint-disable-next-line no-console
        console.error(`Backend exited with code ${code}`);
      }
    });

    await this.waitForHealth(port);
    return { host: this.host, port, token };
  }

  stop(): void {
    if (this.proc && !this.proc.killed) {
      this.proc.kill();
      this.proc = null;
    }
  }

  private findFreePort(): Promise<number> {
    return new Promise((resolve, reject) => {
      const server = net.createServer();
      server.unref();
      server.on('error', reject);
      server.listen(0, this.host, () => {
        const addr = server.address();
        const port = typeof addr === 'object' && addr ? addr.port : 0;
        server.close(() => resolve(port));
      });
    });
  }

  private waitForHealth(port: number, timeoutMs = 20000): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    const url = `http://${this.host}:${port}/health`;
    return new Promise((resolve, reject) => {
      const attempt = () => {
        http
          .get(url, (res) => {
            res.resume();
            if (res.statusCode === 200) resolve();
            else retry();
          })
          .on('error', retry);
      };
      const retry = () => {
        if (Date.now() > deadline) reject(new Error('Backend health check timed out'));
        else setTimeout(attempt, 400);
      };
      attempt();
    });
  }
}

// Keep a reference so bundlers do not tree-shake the app import.
void app;
