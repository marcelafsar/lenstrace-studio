// Types mirroring the backend delivery DTOs (backend/api/routes_delivery.py
// and core/delivery/models.py).

export type ProviderId = 'icloud_photos' | 'pairdrop' | 'apple_devices';

export type AvailabilityLevel = 'ready' | 'needs_setup' | 'unavailable';

export type DeliveryState =
  | 'unavailable'
  | 'ready'
  | 'preparing'
  | 'awaiting_user'
  | 'copying'
  | 'opening_external_app'
  | 'verifying'
  | 'waiting_for_sync'
  | 'completed'
  | 'cancelled'
  | 'failed';

export interface DeliveryAvailability {
  provider_id: ProviderId;
  level: AvailabilityLevel;
  recommended: boolean;
  summary: string;
  details: Record<string, string>;
}

export interface ProvidersResponse {
  providers: DeliveryAvailability[];
  sync_folder_name: string;
  pairdrop_default_url: string;
}

export interface ExportFileInfo {
  filename: string;
  image_format?: string | null;
  mime_type?: string | null;
  width?: number | null;
  height?: number | null;
  size_bytes: number;
  sha256: string;
  exif_make?: string | null;
  exif_model?: string | null;
  lens_model?: string | null;
  datetime_original?: string | null;
  offset_time_original?: string | null;
  gps_summary: string;
}

export interface UserAction {
  title: string;
  instructions: string[];
  open_url?: string | null;
  open_app?: string | null;
  open_folder: boolean;
}

export interface ProviderPreparation {
  provider_id: ProviderId;
  ready_to_execute: boolean;
  destination_name?: string | null;
  destination_label?: string | null;
  user_action?: UserAction | null;
  warnings: string[];
  notes: string[];
}

export interface DeliveryOptions {
  destination_dir?: string | null;
  verify_checksum?: boolean;
  verify_metadata?: boolean;
  collision_strategy?: string;
  extra?: Record<string, string>;
}

export interface PrepareResponse {
  job_id: string;
  preparation: ProviderPreparation;
  source_info: ExportFileInfo;
}

export interface DeliveryJobStatus {
  job_id: string;
  provider_id: ProviderId;
  state: DeliveryState;
  progress: number;
  message: string;
  destination_name?: string | null;
  destination_verified?: boolean | null;
  source_info?: ExportFileInfo | null;
  warnings: string[];
  errors: string[];
  user_action?: UserAction | null;
  completed: boolean;
  cancelled: boolean;
}

export interface ValidateUrlResponse {
  valid: boolean;
  normalized?: string | null;
  hostname?: string | null;
  is_default: boolean;
  error?: string | null;
}
