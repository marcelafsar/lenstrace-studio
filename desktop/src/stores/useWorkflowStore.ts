import { create } from 'zustand';
import type {
  ExposureMode,
  GPSInput,
  MetadataSummary,
  ResolutionFit,
  ResolutionMode,
  UploadedFile,
} from '@/types';

export type Step =
  | 'select'
  | 'inspect'
  | 'device'
  | 'camera'
  | 'datetime'
  | 'location'
  | 'review'
  | 'export';

export const STEP_ORDER: Step[] = [
  'select',
  'inspect',
  'device',
  'camera',
  'datetime',
  'location',
  'review',
  'export',
];

export interface WorkingFile {
  file: UploadedFile;
  summary?: MetadataSummary;
}

/** Date/time configuration collected in the workflow. */
export interface DateTimeConfig {
  mode: 'keep' | 'set';
  datetime: string; // "YYYY-MM-DD HH:MM:SS"
  timezone: string; // IANA name
  utcOffset: string; // "+02:00"
}

/** Location configuration collected in the workflow. */
export interface LocationConfig {
  mode: 'keep' | 'set' | 'remove';
  gps: GPSInput | null;
}

export interface ExportOptions {
  outputDir: string | null;
  filenameSuffix: string;
  preserveName: boolean;
  writeAudit: boolean;
  onCollision: 'increment' | 'overwrite' | 'error';
}

/** Camera-exposure simulation configuration. */
export interface ExposureConfig {
  mode: ExposureMode;
  profileId: string;
  autoFill: boolean;
  // Custom values (used when mode === 'custom').
  iso: string;
  shutter: string;
  ev: string;
  flashFired: boolean;
}

/** Output-resolution configuration. */
export interface ResolutionConfig {
  mode: ResolutionMode;
  fit: ResolutionFit;
  customWidth: string;
  customHeight: string;
}

interface WorkflowState {
  step: Step;
  files: WorkingFile[];
  activeIndex: number;

  presetId: string | null;
  lensId: string | null;
  software: string | null;

  dateTime: DateTimeConfig;
  location: LocationConfig;
  options: ExportOptions;
  exposure: ExposureConfig;
  resolution: ResolutionConfig;

  // actions
  setStep: (step: Step) => void;
  next: () => void;
  back: () => void;
  setFiles: (files: WorkingFile[]) => void;
  addFiles: (files: WorkingFile[]) => void;
  setSummary: (fileId: string, summary: MetadataSummary) => void;
  removeFile: (fileId: string) => void;
  setActiveIndex: (i: number) => void;
  setDevice: (presetId: string | null, lensId: string | null) => void;
  setSoftware: (value: string | null) => void;
  setDateTime: (cfg: Partial<DateTimeConfig>) => void;
  setLocation: (cfg: Partial<LocationConfig>) => void;
  setOptions: (opts: Partial<ExportOptions>) => void;
  setExposure: (cfg: Partial<ExposureConfig>) => void;
  setResolution: (cfg: Partial<ResolutionConfig>) => void;
  reset: () => void;
}

const initialDateTime: DateTimeConfig = {
  mode: 'keep',
  datetime: '',
  timezone: 'UTC',
  utcOffset: '+00:00',
};

const initialLocation: LocationConfig = { mode: 'keep', gps: null };

const initialOptions: ExportOptions = {
  outputDir: null,
  filenameSuffix: '_metadata',
  preserveName: false,
  writeAudit: true,
  onCollision: 'increment',
};

const initialExposure: ExposureConfig = {
  mode: 'preserve',
  profileId: 'default',
  autoFill: true,
  iso: '',
  shutter: '',
  ev: '0',
  flashFired: false,
};

const initialResolution: ResolutionConfig = {
  mode: 'keep',
  fit: 'crop_to_fill',
  customWidth: '',
  customHeight: '',
};

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  step: 'select',
  files: [],
  activeIndex: 0,
  presetId: null,
  lensId: null,
  software: null,
  dateTime: initialDateTime,
  location: initialLocation,
  options: initialOptions,
  exposure: initialExposure,
  resolution: initialResolution,

  setStep: (step) => set({ step }),
  next: () => {
    const i = STEP_ORDER.indexOf(get().step);
    if (i < STEP_ORDER.length - 1) set({ step: STEP_ORDER[i + 1] });
  },
  back: () => {
    const i = STEP_ORDER.indexOf(get().step);
    if (i > 0) set({ step: STEP_ORDER[i - 1] });
  },
  setFiles: (files) => set({ files, activeIndex: 0 }),
  addFiles: (files) => set({ files: [...get().files, ...files] }),
  setSummary: (fileId, summary) =>
    set({
      files: get().files.map((f) =>
        f.file.file_id === fileId ? { ...f, summary } : f
      ),
    }),
  removeFile: (fileId) =>
    set({ files: get().files.filter((f) => f.file.file_id !== fileId) }),
  setActiveIndex: (i) => set({ activeIndex: i }),
  setDevice: (presetId, lensId) => set({ presetId, lensId }),
  setSoftware: (value) => set({ software: value }),
  setDateTime: (cfg) => set({ dateTime: { ...get().dateTime, ...cfg } }),
  setLocation: (cfg) => set({ location: { ...get().location, ...cfg } }),
  setOptions: (opts) => set({ options: { ...get().options, ...opts } }),
  setExposure: (cfg) => set({ exposure: { ...get().exposure, ...cfg } }),
  setResolution: (cfg) => set({ resolution: { ...get().resolution, ...cfg } }),
  reset: () =>
    set({
      step: 'select',
      files: [],
      activeIndex: 0,
      presetId: null,
      lensId: null,
      software: null,
      dateTime: initialDateTime,
      location: initialLocation,
      options: initialOptions,
      exposure: initialExposure,
      resolution: initialResolution,
    }),
}));
