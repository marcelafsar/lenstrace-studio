import { useState } from 'react';
import { Banner } from '@/components/Banner';
import { api, ApiError } from '@/services/api';
import { buildChangeRequest } from '@/services/buildRequest';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useExportsStore } from '@/stores/useExportsStore';
import { useNavStore } from '@/stores/useNavStore';

interface FileOutcome {
  name: string;
  ok: boolean;
  destination?: string;
  audit?: string | null;
  warnings?: string[];
  error?: string;
}

export function ExportPage() {
  const files = useWorkflowStore((s) => s.files);
  const options = useWorkflowStore((s) => s.options);
  const setOptions = useWorkflowStore((s) => s.setOptions);
  const back = useWorkflowStore((s) => s.back);
  const reset = useWorkflowStore((s) => s.reset);
  const addExport = useExportsStore((s) => s.add);
  const goToSection = useNavStore((s) => s.setSection);

  const [running, setRunning] = useState(false);
  const [anyDelivered, setAnyDelivered] = useState(false);
  const [done, setDone] = useState(false);
  const [outcomes, setOutcomes] = useState<FileOutcome[]>([]);
  const [lastFolder, setLastFolder] = useState<string | null>(null);

  const chooseFolder = async () => {
    const dir = await window.lenstrace?.chooseOutputDir();
    if (dir) setOptions({ outputDir: dir });
  };

  const runExport = async () => {
    setRunning(true);
    setDone(false);
    const results: FileOutcome[] = [];
    for (const f of files) {
      const req = buildChangeRequest(f.file.file_id, useWorkflowStore.getState());
      try {
        const res = await api.export(req);
        results.push({
          name: f.file.original_name,
          ok: true,
          destination: res.result.destination_path,
          audit: res.result.audit_sidecar_path,
          warnings: res.result.warnings,
        });
        setLastFolder(res.result.destination_path.replace(/[\\/][^\\/]*$/, ''));
        // Record the export so it can be sent to an iPhone from "Send to iPhone".
        if (res.export_id) {
          addExport({
            exportId: res.export_id,
            name: res.result.destination_path.replace(/^.*[\\/]/, ''),
            thumbnailDataUri: f.file.thumbnail_data_uri,
          });
          setAnyDelivered(true);
        }
      } catch (e) {
        results.push({
          name: f.file.original_name,
          ok: false,
          error: e instanceof ApiError ? e.message : String(e),
        });
      }
    }
    setOutcomes(results);
    setRunning(false);
    setDone(true);
  };

  const okCount = outcomes.filter((o) => o.ok).length;

  return (
    <div className="content-inner">
      <h1 className="page-title">Export</h1>
      <p className="page-sub">
        Write a new copy for {files.length} image{files.length === 1 ? '' : 's'}. Originals are
        never modified.
      </p>

      <div className="panel">
        <label className="field">
          <span>Output folder</span>
          <div className="inline-fields">
            <input type="text" readOnly value={options.outputDir ?? '(default: Pictures/LensTrace Output)'} />
            <button className="btn" style={{ flex: 'none' }} onClick={chooseFolder}>
              Choose…
            </button>
          </div>
        </label>

        <div className="inline-fields">
          <label className="field">
            <span>Filename suffix</span>
            <input
              type="text"
              value={options.filenameSuffix}
              disabled={options.preserveName}
              onChange={(e) => setOptions({ filenameSuffix: e.target.value })}
            />
          </label>
          <label className="field">
            <span>On name collision</span>
            <select
              value={options.onCollision}
              onChange={(e) => setOptions({ onCollision: e.target.value as never })}
            >
              <option value="increment">Add a number</option>
              <option value="overwrite">Overwrite</option>
              <option value="error">Stop with error</option>
            </select>
          </label>
        </div>

        <label className="field" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="checkbox"
            style={{ width: 'auto' }}
            checked={options.preserveName}
            onChange={(e) => setOptions({ preserveName: e.target.checked })}
          />
          <span style={{ margin: 0 }}>Preserve original filename</span>
        </label>
        <label className="field" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="checkbox"
            style={{ width: 'auto' }}
            checked={options.writeAudit}
            onChange={(e) => setOptions({ writeAudit: e.target.checked })}
          />
          <span style={{ margin: 0 }}>Write JSON audit sidecar</span>
        </label>
      </div>

      {done && (
        <Banner kind={okCount === files.length ? 'success' : 'warn'}>
          Exported {okCount} of {files.length} file{files.length === 1 ? '' : 's'}.
        </Banner>
      )}

      {outcomes.length > 0 && (
        <div className="panel">
          <table className="diff-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {outcomes.map((o) => (
                <tr key={o.name}>
                  <td>{o.name}</td>
                  <td>
                    {o.ok ? (
                      <>
                        <span className="tag added">exported</span>{' '}
                        {o.warnings && o.warnings.length > 0 && (
                          <span className="hint">{o.warnings.join(' ')}</span>
                        )}
                      </>
                    ) : (
                      <span className="tag removed" title={o.error}>
                        failed
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="btn-row">
        <button className="btn ghost" onClick={back} disabled={running}>
          Back
        </button>
        <span className="spacer" />
        {done && lastFolder && (
          <button className="btn" onClick={() => window.lenstrace?.openPath(lastFolder)}>
            Open output folder
          </button>
        )}
        {done && anyDelivered && (
          <button className="btn primary" onClick={() => goToSection('send')}>
            Send to iPhone →
          </button>
        )}
        {done ? (
          <button className="btn ghost" onClick={reset}>
            Start over
          </button>
        ) : (
          <button className="btn primary" onClick={runExport} disabled={running}>
            {running ? 'Exporting…' : `Export ${files.length} file${files.length === 1 ? '' : 's'}`}
          </button>
        )}
      </div>
    </div>
  );
}
