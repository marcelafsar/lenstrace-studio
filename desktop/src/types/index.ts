// Shared TypeScript types mirroring the backend DTOs (backend/api/schemas.py).

export interface BackendConnection {
  host: string;
  port: number;
  token: string;
}

export interface PickedFile {
  path: string;
  name: string;
  bytes: string; // base64
}

export interface UploadedFile {
  file_id: string;
  original_name: string;
  image_format: string;
  width?: number | null;
  height?: number | null;
  thumbnail_data_uri?: string | null;
}

export interface MetadataSummary {
  image_format: string;
  width?: number | null;
  height?: number | null;
  make?: string | null;
  model?: string | null;
  lens_model?: string | null;
  software?: string | null;
  datetime_original?: string | null;
  create_date?: string | null;
  modify_date?: string | null;
  offset_time_original?: string | null;
  gps_latitude?: number | null;
  gps_longitude?: number | null;
  gps_altitude_m?: number | null;
  has_gps: boolean;
  raw_tags: Record<string, string>;
}

export interface Lens {
  id: string;
  display_name: string;
  lens_model: string;
}

export interface Device {
  id: string;
  display_name: string;
  generation?: string | null;
  exif_model: string;
  source_status: string;
  lenses: Lens[];
  notes: string;
}

export interface PresetsResponse {
  schema_version: number;
  devices: Device[];
}

export interface GPSInput {
  latitude: number;
  longitude: number;
  altitude_m?: number | null;
  address_label?: string | null;
}

export interface ChangeRequest {
  file_id: string;
  output_dir?: string | null;
  preset_id?: string | null;
  lens_id?: string | null;
  make?: string | null;
  model?: string | null;
  lens_model?: string | null;
  software?: string | null;
  set_datetime?: boolean;
  datetime_original?: string | null;
  timezone_name?: string | null;
  utc_offset?: string | null;
  gps?: GPSInput | null;
  remove_gps?: boolean;
  strip_all_metadata?: boolean;
  write_audit_sidecar?: boolean;
  filename_suffix?: string;
  preserve_name?: boolean;
  on_collision?: string;
}

export interface FieldChange {
  field: string;
  original?: string | null;
  new?: string | null;
  status: 'added' | 'changed' | 'removed' | 'preserved';
}

export interface ChangeDiff {
  rows: FieldChange[];
}

export interface PreviewResponse {
  diff: ChangeDiff;
  destination_name: string;
  disclaimer: string;
}

export interface ExportResult {
  source_path: string;
  destination_path: string;
  audit_sidecar_path?: string | null;
  bytes_written: number;
  converted_to_jpeg: boolean;
  warnings: string[];
  success: boolean;
}

export interface ExportResponse {
  result: ExportResult;
  disclaimer: string;
}
