import { useEffect, useState } from 'react';
import QRCode from 'qrcode';

/**
 * Renders a QR code for a URL, generated entirely offline (no network). The
 * payload is ONLY the provided URL — never file bytes, paths, tokens, or
 * metadata.
 */
export function QrCode({ url, size = 180 }: { url: string; size?: number }) {
  const [dataUri, setDataUri] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    QRCode.toDataURL(url, { width: size, margin: 1, errorCorrectionLevel: 'M' })
      .then((uri) => !cancelled && setDataUri(uri))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [url, size]);

  if (error) return <p className="hint">Could not render QR code.</p>;
  if (!dataUri) return <div style={{ width: size, height: size }} />;
  return (
    <img
      src={dataUri}
      alt={`QR code for ${url}`}
      width={size}
      height={size}
      style={{ borderRadius: 8, background: '#fff', padding: 6 }}
    />
  );
}
