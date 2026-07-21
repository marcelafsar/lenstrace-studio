import type { ChangeRequest } from '@/types';
import { useWorkflowStore } from '@/stores/useWorkflowStore';

type Store = ReturnType<typeof useWorkflowStore.getState>;

/** Assemble a backend ChangeRequest for a single file from the workflow state. */
export function buildChangeRequest(fileId: string, state: Store): ChangeRequest {
  const { presetId, lensId, software, dateTime, location, options } = state;

  const req: ChangeRequest = {
    file_id: fileId,
    output_dir: options.outputDir,
    preset_id: presetId,
    lens_id: lensId,
    software,
    set_datetime: dateTime.mode === 'set',
    write_audit_sidecar: options.writeAudit,
    filename_suffix: options.filenameSuffix,
    preserve_name: options.preserveName,
    on_collision: options.onCollision,
    remove_gps: location.mode === 'remove',
  };

  if (dateTime.mode === 'set' && dateTime.datetime) {
    req.datetime_original = dateTime.datetime;
    req.timezone_name = dateTime.timezone;
    req.utc_offset = dateTime.utcOffset;
  }

  if (location.mode === 'set' && location.gps) {
    req.gps = location.gps;
  }

  return req;
}
