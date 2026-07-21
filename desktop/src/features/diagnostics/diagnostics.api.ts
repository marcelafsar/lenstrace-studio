import { request } from '@/services/api';

export type CheckStatus = 'PASS' | 'WARN' | 'FAIL';

export interface CheckResult {
  name: string;
  status: CheckStatus;
  category: string;
  detail: string;
  config_invalid: boolean;
}

export interface CheckReport {
  results: CheckResult[];
  passed: number;
  warned: number;
  failed: number;
  config_invalid: boolean;
}

export const diagnosticsApi = {
  status: (connectivity = false) =>
    request<{ report: CheckReport }>(
      `/config/status?connectivity=${connectivity ? 'true' : 'false'}`
    ),
  recheck: (connectivity = false) =>
    request<{ report: CheckReport }>(
      `/config/recheck?connectivity=${connectivity ? 'true' : 'false'}`,
      { method: 'POST' }
    ),
};
