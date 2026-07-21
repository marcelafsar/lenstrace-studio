import { request } from '@/services/api';
import type {
  DeliveryJobStatus,
  DeliveryOptions,
  PrepareResponse,
  ProviderId,
  ProvidersResponse,
  ValidateUrlResponse,
} from './delivery.types';

export const deliveryApi = {
  providers: () => request<ProvidersResponse>('/delivery/providers'),

  validateUrl: (url: string) =>
    request<ValidateUrlResponse>('/delivery/validate-url', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),

  prepare: (provider: ProviderId, exportId: string, options: DeliveryOptions = {}) =>
    request<PrepareResponse>(`/delivery/${provider}/prepare`, {
      method: 'POST',
      body: JSON.stringify({ export_id: exportId, options }),
    }),

  execute: (jobId: string) =>
    request<DeliveryJobStatus>(`/delivery/jobs/${jobId}/execute`, { method: 'POST' }),

  status: (jobId: string) => request<DeliveryJobStatus>(`/delivery/jobs/${jobId}`),

  cancel: (jobId: string) =>
    request<DeliveryJobStatus>(`/delivery/jobs/${jobId}/cancel`, { method: 'POST' }),
};
