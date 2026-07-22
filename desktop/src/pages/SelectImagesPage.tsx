import { useState } from 'react';
import { DropZone } from '@/components/DropZone';
import { Banner } from '@/components/Banner';
import { PageNav } from '@/components/PageNav';
import { api, ApiError } from '@/services/api';
import { useWorkflowStore, type WorkingFile } from '@/stores/useWorkflowStore';

export function SelectImagesPage() {
  const files = useWorkflowStore((s) => s.files);
  const addFiles = useWorkflowStore((s) => s.addFiles);
  const removeFile = useWorkflowStore((s) => s.removeFile);
  const activeIndex = useWorkflowStore((s) => s.activeIndex);
  const setActiveIndex = useWorkflowStore((s) => s.setActiveIndex);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (items: { name: string; base64: string }[]) => {
    setBusy(true);
    setError(null);
    try {
      const uploaded: WorkingFile[] = [];
      for (const item of items) {
        const file = await api.uploadFile(item.name, item.base64);
        uploaded.push({ file });
      }
      addFiles(uploaded);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const pickNative = async () => {
    if (!window.lenstrace) return;
    const picked = await window.lenstrace.openImages();
    if (picked.length) {
      await upload(picked.map((p) => ({ name: p.name, base64: p.bytes })));
    }
  };

  return (
    <div className="content-inner">
      <h1 className="page-title">Select images</h1>
      <p className="page-sub">
        Add one or more photos. Originals are never modified — every export writes a new copy.
      </p>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="panel">
        <DropZone
          onFiles={upload}
          onPickNative={pickNative}
        />
        {busy && <p className="hint">Uploading…</p>}

        {files.length > 0 && (
          <div className="file-grid">
            {files.map((f, i) => (
              <div
                key={f.file.file_id}
                className={`file-card ${i === activeIndex ? 'active' : ''}`}
                onClick={() => setActiveIndex(i)}
              >
                <button
                  className="remove"
                  title="Remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    api.deleteFile(f.file.file_id).catch(() => undefined);
                    removeFile(f.file.file_id);
                  }}
                >
                  ×
                </button>
                {f.file.thumbnail_data_uri ? (
                  <img src={f.file.thumbnail_data_uri} alt={f.file.original_name} />
                ) : (
                  <div style={{ aspectRatio: '4 / 3' }} />
                )}
                <div className="meta">
                  <div className="name" title={f.file.original_name}>
                    {f.file.original_name}
                  </div>
                  <div className="hint">
                    {f.file.image_format} · {f.file.width}×{f.file.height}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <PageNav hideBack nextDisabled={files.length === 0} nextLabel="Inspect" />
    </div>
  );
}
