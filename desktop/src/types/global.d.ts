import type { BackendConnection, PickedFile } from './index';

declare global {
  interface Window {
    lenstrace: {
      getConnection: () => Promise<BackendConnection>;
      openImages: () => Promise<PickedFile[]>;
      chooseOutputDir: () => Promise<string | null>;
      openPath: (target: string) => Promise<string>;
    };
  }
}

export {};
