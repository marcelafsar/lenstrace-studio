import { useState, type DragEvent } from 'react';

interface Props {
  onFiles: (files: { name: string; base64: string }[]) => void;
  onPickNative: () => void;
}

async function fileToBase64(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  let binary = '';
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export function DropZone({ onFiles, onPickNative }: Props) {
  const [drag, setDrag] = useState(false);

  const handleDrop = async (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      f.type.startsWith('image/') || /\.(jpe?g|png|tiff?|webp|heic|heif)$/i.test(f.name)
    );
    const encoded = await Promise.all(
      dropped.map(async (f) => ({ name: f.name, base64: await fileToBase64(f) }))
    );
    if (encoded.length) onFiles(encoded);
  };

  return (
    <div
      className={`dropzone ${drag ? 'drag' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      onClick={onPickNative}
      role="button"
      tabIndex={0}
    >
      <p style={{ fontSize: 15 }}>
        <strong>Drag &amp; drop images here</strong>
      </p>
      <p className="hint">JPEG, PNG, TIFF, WebP, HEIC/HEIF · or click to browse</p>
    </div>
  );
}
