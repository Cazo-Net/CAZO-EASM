// Types for the AI Intelligence Engine (multi-provider + recommendations).

export type AIProviderId = "openai" | "anthropic" | "ollama" | "stub";

export type AIRecordStatus =
  | "open"
  | "in_progress"
  | "resolved"
  | "dismissed"
  | "deferred"
  | "pending";

export type AIRecordPriority = "low" | "medium" | "high" | "critical";

export interface ProviderInfo {
  id: AIProviderId;
  name: string;
  configured: boolean;
  default_model: string;
}

export interface ProviderStatusResponse {
  providers: ProviderInfo[];
  active_provider: AIProviderId;
  active_model: string;
}

export interface AISettings {
  provider: AIProviderId;
  model: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
}

export interface AIRecommendation {
  id: string;
  user_id?: string;
  org_id?: string | null;
  category: string;
  title: string;
  description: string;
  priority: AIRecordPriority;
  entity_type?: string | null;
  entity_id?: string | null;
  status: AIRecordStatus;
  dismissed?: boolean;
  created_at?: string;
}

export interface AIRecommendationListResponse {
  recommendations: AIRecommendation[];
  total?: number;
  open?: number;
  critical?: number;
}
