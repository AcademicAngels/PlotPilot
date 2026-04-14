import { apiClient } from './config'

export interface LlmProviderExample {
  name: string
  llm_provider: 'anthropic' | 'openai'
  base_url: string
  model: string
  api_mode: 'auto' | 'chat' | 'responses'
  notes: string
}

export interface LlmProviderConfigResponse {
  llm_provider: 'anthropic' | 'openai'
  has_api_key: boolean
  api_key_masked: string | null
  base_url: string
  model: string
  api_mode: 'auto' | 'chat' | 'responses'
  timeout: number
  max_retries: number
  embedding_model: string
  embedding_dimension: number | null
  examples: LlmProviderExample[]
}

export interface UpdateLlmProviderConfigRequest {
  llm_provider: 'anthropic' | 'openai'
  api_key?: string
  clear_api_key?: boolean
  base_url: string
  model: string
  api_mode: 'auto' | 'chat' | 'responses'
  timeout: number
  max_retries: number
  embedding_model: string
  embedding_dimension?: number | null
}

export const llmConfigApi = {
  getConfig: () =>
    apiClient.get<LlmProviderConfigResponse>('/settings/llm-provider'),

  updateConfig: (payload: UpdateLlmProviderConfigRequest) =>
    apiClient.put<LlmProviderConfigResponse>('/settings/llm-provider', payload),
}
