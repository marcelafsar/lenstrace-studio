import type { ChangeRequest } from '@/types';
import { useWorkflowStore } from '@/stores/useWorkflowStore';

type Store = ReturnType<typeof useWorkflowStore.getState>;

/** Assemble a backend ChangeRequest for a single file from the workflow state. */
export function buildChangeRequest(fileId: string, state: Store): ChangeRequest {
  const { presetId, lensId, software, dateTime, location, options, exposure, resolution } = state;

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
    exposure_mode: exposure.mode,
    exposure_profile_id: exposure.profileId,
    auto_fill_exposure: exposure.autoFill,
    resolution_mode: resolution.mode,
    resolution_fit: resolution.fit,
  };

  if (dateTime.mode === 'set' && dateTime.datetime) {
    req.datetime_original = dateTime.datetime;
    req.timezone_name = dateTime.timezone;
    req.utc_offset = dateTime.utcOffset;
  }

  if (location.mode === 'set' && location.gps) {
    req.gps = location.gps;
  }

  if (exposure.mode === 'custom') {
    req.exposure_iso = exposure.iso ? Number(exposure.iso) : null;
    req.exposure_shutter = exposure.shutter || null;
    req.exposure_ev = exposure.ev ? Number(exposure.ev) : 0;
    req.exposure_flash_fired = exposure.flashFired;
  }

  if (resolution.mode === 'custom') {
    req.custom_width = resolution.customWidth ? Number(resolution.customWidth) : null;
    req.custom_height = resolution.customHeight ? Number(resolution.customHeight) : null;
  }

  return req;
}
