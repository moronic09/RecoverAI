import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, ChevronDown, ChevronUp, RefreshCw, Brain, Zap, Check, X, Clock } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api, Transaction } from '@/lib/api'
import { formatCurrency, formatReason, formatPercent } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { FadeIn } from '@/components/ui/CountUp'

export default function TransactionsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data: transactions, isLoading } = useQuery({
    queryKey: ['transactions', statusFilter, search],
    queryFn: () => api.getTransactions({ status: statusFilter || undefined, search: search || undefined, limit: 100 }),
    refetchInterval: 15000,
  })

  const retryMutation = useMutation({
    mutationFn: (id: number) => api.retry(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['transactions'] }),
  })

  const predictMutation = useMutation({
    mutationFn: (id: number) => api.predict(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['transactions'] }),
  })

  return (
    <div className="ledger-page">
      <div>
        <p className="eyebrow">Payment ledger / recovery decisions</p>
        <h1 className="font-serif text-5xl font-bold tracking-tight">Transactions</h1>
        <p className="text-slate-500 mt-2">Every failed payment, weighed against the cost of pursuing it.</p>
      </div>

      <div className="flex gap-4 flex-wrap py-7 border-b border-paper-line">
        <div className="relative flex-1 min-w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by payment ID, customer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-transparent border-b border-paper-line focus:border-ink focus:outline-none"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2.5 bg-transparent border-b border-paper-line focus:border-ink focus:outline-none"
        >
          <option value="">All statuses</option>
          <option value="failed">Failed</option>
          <option value="captured">Captured</option>
        </select>
      </div>

      <div className="mt-6 overflow-hidden">
        {isLoading ? (
          <TransactionSkeleton />
        ) : !transactions?.length ? (
          <div className="p-10 text-center text-slate-500">No transactions match your filters</div>
        ) : (
          <div className="divide-y divide-paper-line">
            {transactions.map((tx, i) => (
              <FadeIn key={tx.id} delay={i * 0.03}>
                <TransactionRow
                  tx={tx}
                  expanded={expandedId === tx.id}
                  onToggle={() => setExpandedId(expandedId === tx.id ? null : tx.id)}
                  onRetry={() => retryMutation.mutate(tx.id)}
                  onPredict={() => predictMutation.mutate(tx.id)}
                  retrying={retryMutation.isPending}
                />
              </FadeIn>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TransactionRow({
  tx,
  expanded,
  onToggle,
  onRetry,
  onPredict,
  retrying,
}: {
  tx: Transaction
  expanded: boolean
  onToggle: () => void
  onRetry: () => void
  onPredict: () => void
  retrying: boolean
}) {
  const pred = tx.latest_prediction
  const importances = pred?.feature_importances
    ? Object.entries(pred.feature_importances)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 6)
        .map(([name, value]) => ({ name: name.replace(/_/g, ' '), value: value * 100 }))
    : []

  return (
    <div>
      <div
        className="flex items-center gap-4 py-5 border-b border-paper-line hover:bg-[#EFEBE2] cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0 grid grid-cols-1 md:grid-cols-5 gap-2 items-center">
          <div>
            <p className="font-mono text-sm text-slate-300 truncate">{tx.razorpay_payment_id}</p>
            <p className="text-xs text-slate-500">{new Date(tx.created_at).toLocaleString()}</p>
          </div>
          <p className="font-mono text-right text-sm">{formatCurrency(Number(tx.amount))}</p>
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${tx.status === 'captured' ? 'text-revival' : tx.status === 'failed' ? 'text-flatline' : 'text-amber-700'}`}>
            {tx.status === 'captured' ? <Check className="w-3 h-3" aria-hidden="true" /> : tx.status === 'failed' ? <X className="w-3 h-3" aria-hidden="true" /> : <Clock className="w-3 h-3" aria-hidden="true" />} {tx.status}
          </span>
          <p className="text-sm text-slate-400 capitalize">{tx.payment_method}</p>
          <div className="flex items-center gap-2">
            {tx.customer_failure_count_30d >= 2 && <span className="text-xs text-flatline">repeat {tx.customer_failure_count_30d}x</span>}
            {pred && (
                <span className="text-xs font-mono text-revival">
                {formatPercent((tx.fatigue_adjusted_probability ?? pred.recovery_probability) * 100)} recovery
              </span>
            )}
            {expanded ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
          </div>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-5 grid grid-cols-1 lg:grid-cols-2 gap-4 bg-[#EFEBE2]">
              <div className="space-y-3 p-4 border border-paper-line">
                <h4 className="font-semibold flex items-center gap-2">
                  <Brain className="w-4 h-4 text-brand-400" />
                  ML Analysis
                </h4>
                {pred ? (
                  <div className="space-y-2 text-sm">
                    <p className="border-b border-paper-line pb-3 text-xs leading-relaxed text-slate-600">
                      {transactionSummary(tx, pred.recovery_probability)}
                    </p>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Predicted cause</span>
                      <span>{formatReason(pred.predicted_failure_class)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Confidence</span>
                      <span>{formatPercent(pred.failure_confidence * 100)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Recovery probability</span>
                      <span className="text-revival font-semibold">{formatPercent((tx.fatigue_adjusted_probability ?? pred.recovery_probability) * 100)} <span className="text-xs text-slate-500">({tx.confidence || 'medium'} confidence)</span></span>
                    </div>
                    <p className="border-l-2 border-revival pl-3 text-xs leading-relaxed text-slate-600">
                      {recoveryReason(tx, pred.recovery_probability)}
                    </p>
                    <div className="border-t border-paper-line pt-3 text-xs text-slate-600">
                      <span className="font-medium">ROI decision:</span> {tx.recommendation || 'Pending'} · expected value {formatCurrency(tx.expected_value ?? 0)} after {formatCurrency(tx.estimated_retry_cost ?? 0)} cost
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Recommended channel</span>
                      <span className="text-revival">→ {tx.recommended_channel_label || 'Review'}</span>
                    </div>
                    {tx.customer_failure_count_30d >= 2 && <p className="border-l-2 border-flatline pl-3 text-xs text-slate-600">Customer has failed {tx.customer_failure_count_30d}x in the last 30 days. Recovery likelihood adjusted down for fatigue.</p>}
                    {tx.explainability.length > 0 && <div className="border-t border-paper-line pt-3"><p className="eyebrow mb-2">Why this score</p>{tx.explainability.map((factor) => <div className="flex items-center justify-between gap-3 border-b border-paper-line py-2 text-xs" key={factor.factor_name}><span>{factor.factor_name}</span><span className={factor.direction === '+' ? 'positive-ink' : 'negative-ink'}>{factor.direction} {factor.impact_description}</span></div>)}</div>}
                    <div className="flex justify-between">
                      <span className="text-slate-400">Recommended action</span>
                      <span className="text-revival">{tx.recommended_channel_label || formatReason(pred.recommended_action)}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No prediction yet</p>
                )}

                <div className="flex gap-2 pt-2">
                  {!pred && (
                    <Button size="sm" variant="secondary" onClick={(e) => { e.stopPropagation(); onPredict() }}>
                      <Brain className="w-3 h-3" /> Run ML
                    </Button>
                  )}
                  {tx.status === 'failed' && (
                    <Button size="sm" onClick={(e) => { e.stopPropagation(); onRetry() }} loading={retrying}>
                      <RefreshCw className="w-3 h-3" /> Retry
                    </Button>
                  )}
                </div>
              </div>

              {importances.length > 0 && (
                <div className="p-4 border border-paper-line">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-400" />
                    Feature Importances
                  </h4>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={importances} layout="vertical">
                      <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                      <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} width={100} />
                      <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                        {importances.map((_, i) => (
                          <Cell key={i} fill={`hsl(${240 + i * 15}, 70%, 60%)`} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function recoveryReason(tx: Transaction, probability: number) {
  if (probability >= 0.7) {
    return `High recovery chance: repeat customer (${tx.customer_failure_history} prior failures), and ${formatReason(tx.failure_reason || 'payment')} failures often resolve after a follow-up retry.`
  }
  if (probability >= 0.4) {
    return 'Moderate recovery chance: retry after a short delay while the customer can use another payment attempt.'
  }
  return 'Lower recovery chance: send an update-payment-method message before attempting another retry.'
}

function transactionSummary(tx: Transaction, probability: number) {
  const adjusted = tx.fatigue_adjusted_probability ?? probability
  const confidence = tx.confidence || 'medium'
  const channel = tx.recommended_channel_label || 'review'
  const fatigue = tx.customer_failure_count_30d >= 2 ? ', reduced for repeat-customer fatigue' : ''
  return `${confidence[0].toUpperCase()}${confidence.slice(1)} confidence: this ${formatReason(tx.payment_method)} failure has a ${formatPercent(adjusted * 100)} recovery chance${fatigue}. Recommended: ${channel}.`
}

function TransactionSkeleton() {
  return <div className="space-y-px bg-paper-line">
    {Array.from({ length: 6 }).map((_, index) => <div key={index} className="h-20 animate-pulse bg-[#EFEBE2]" />)}
  </div>
}
