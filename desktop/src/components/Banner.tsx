import type { ReactNode } from 'react';

type Kind = 'info' | 'warn' | 'error' | 'success';

export function Banner({ kind = 'info', children }: { kind?: Kind; children: ReactNode }) {
  return <div className={`banner ${kind}`}>{children}</div>;
}
