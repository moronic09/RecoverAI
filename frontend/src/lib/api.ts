const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

function getToken(): string | null {
  return localStorage.getItem('token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  register: (email: string, password: string, name: string) =>
    request<{ access_token: string }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    }),

  getMe: () => request<{ id: number; email: string; name: string }>('/api/auth/me'),

  getSummary: (merchantType?: string) =>
    request<{
      total_transactions: number
      failed_count: number
      recovered_count: number
      recovery_rate: number
      total_failed_amount: number
      total_recovered_amount: number
      pending_retries: number
      avg_recovery_probability: number
    }>(`/api/dashboard/summary${merchantType ? `?merchant_type=${merchantType}` : ''}`),

  getTrend: (days = 365) =>
    request<Array<{ date: string; failed: number; recovered: number; recovery_rate: number }>>(
      `/api/dashboard/trend?days=${days}`
    ),

  getFailureBreakdown: () =>
    request<
      Array<{ reason: string; count: number; percentage: number; avg_recovery_probability: number }>
    >('/api/dashboard/failure-breakdown'),

  getFeatureImportances: () => request<Record<string, number>>('/api/dashboard/feature-importances'),

  getStrategyComparison: (merchantType?: string, minimumExpectedValue = 0) => {
    const params = new URLSearchParams()
    if (merchantType) params.set('merchant_type', merchantType)
    params.set('minimum_expected_value', String(minimumExpectedValue))
    return request<StrategyComparison>(`/api/dashboard/strategy-comparison?${params.toString()}`)
  },

  getABValidation: (merchantType?: string) =>
    request<ABValidation>(`/api/dashboard/ab-validation${merchantType ? `?merchant_type=${merchantType}` : ''}`),

  getTransactions: (params?: { status?: string; search?: string; skip?: number; limit?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.search) qs.set('search', params.search)
    if (params?.skip) qs.set('skip', String(params.skip))
    if (params?.limit) qs.set('limit', String(params.limit))
    return request<Transaction[]>('/api/transactions?' + qs.toString())
  },

  getTransaction: (id: number) => request<Transaction>(`/api/transactions/${id}`),

  predict: (id: number) =>
    request<PredictResult>(`/api/transactions/${id}/predict`, { method: 'POST' }),

  retry: (id: number) =>
    request<{ transaction_id: number; task_id: string; message: string }>(
      `/api/transactions/${id}/retry`,
      { method: 'POST' }
    ),

  toggleLiveFeed: (enabled: boolean) =>
    request<{ enabled: boolean }>('/api/simulation/live-feed', {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),

  getLiveFeedStatus: () => request<{ enabled: boolean }>('/api/simulation/live-feed/status'),
}

export function createWebSocket(onMessage: (data: LiveEvent) => void): WebSocket {
  const ws = new WebSocket(`${WS_URL}/ws/live`)
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.event_type && !['heartbeat', 'pong', 'connected'].includes(data.event_type)) {
        onMessage(data)
      }
    } catch {}
  }
  return ws
}

export interface Transaction {
  id: number
  razorpay_payment_id: string
  amount: number
  currency: string
  status: string
  payment_method: string
  failure_reason: string | null
  failure_code: string | null
  customer_id: string
  customer_email: string | null
  retry_count: number
  customer_failure_history: number
  recovered_amount: number | null
  created_at: string
  latest_prediction?: MLPrediction | null
  estimated_retry_cost?: number | null
  expected_value?: number | null
  recommendation?: string | null
  recommendation_reason?: string | null
  recommended_channel?: string | null
  recommended_channel_label?: string | null
  customer_failure_count_30d: number
  fatigue_adjusted_probability?: number | null
  confidence?: 'high' | 'medium' | 'low' | null
  explainability: Array<{ factor_name: string; direction: string; impact_description: string }>
}

export interface StrategyMetrics {
  recovered_revenue: number
  retry_costs: number
  net_gain: number
}

export interface StrategyComparison {
  naive: StrategyMetrics
  recoverai: StrategyMetrics
  net_gain_difference: number
  transactions_considered: number
  retry_cost_per_attempt: number
}

export interface ABValidationBatch {
  batch: number
  transactions: number
  net_gain_difference: number
  recoverai_wins: boolean
}

export interface ABValidation {
  batches: ABValidationBatch[]
  winning_batches: number
  average_advantage: number
}

export interface MLPrediction {
  id: number
  predicted_failure_class: string
  failure_confidence: number
  recovery_probability: number
  recommended_action: string
  feature_importances: Record<string, number> | null
  created_at: string
}

export interface PredictResult {
  transaction_id: number
  predicted_failure_class: string
  failure_confidence: number
  recovery_probability: number
  recommended_action: string
  feature_importances: Record<string, number>
  feature_values: Record<string, number>
  recommended_channel: string
  confidence: 'high' | 'medium' | 'low'
  explainability: Array<{ factor_name: string; direction: string; impact_description: string }>
  customer_failure_count_30d: number
}

export interface LiveEvent {
  event_type: string
  transaction_id: number
  data: Record<string, unknown>
  timestamp: string
}
