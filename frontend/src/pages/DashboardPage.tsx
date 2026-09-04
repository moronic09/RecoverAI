import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, ArrowDownRight, ArrowUpRight, Check, Radio, X } from 'lucide-react'
import { api, createWebSocket, LiveEvent, StrategyMetrics } from '@/lib/api'
import { formatCurrency, formatPercent, formatReason } from '@/lib/utils'

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([])
  const [liveFeedEnabled, setLiveFeedEnabled] = useState(false)
  const [liveFeedPending, setLiveFeedPending] = useState(false)
  const [pulseKey, setPulseKey] = useState(0)
  const [merchantType, setMerchantType] = useState('')
  const [decisionThreshold, setDecisionThreshold] = useState(0)
  const [appliedThreshold, setAppliedThreshold] = useState(0)
  const { data: summary, isLoading: summaryLoading } = useQuery({ queryKey: ['summary', merchantType], queryFn: () => api.getSummary(merchantType), refetchInterval: 10000 })
  const { data: trend, isLoading: trendLoading } = useQuery({ queryKey: ['trend'], queryFn: () => api.getTrend(365) })
  const { data: strategy, isLoading: strategyLoading, isFetching: strategyFetching } = useQuery({ queryKey: ['strategy-comparison', merchantType, appliedThreshold], queryFn: () => api.getStrategyComparison(merchantType, appliedThreshold), placeholderData: (previous) => previous })
  const { data: abValidation } = useQuery({ queryKey: ['ab-validation', merchantType], queryFn: () => api.getABValidation(merchantType) })
  const { data: breakdown } = useQuery({ queryKey: ['breakdown'], queryFn: api.getFailureBreakdown })

  useEffect(() => { api.getLiveFeedStatus().then((status) => setLiveFeedEnabled(status.enabled)).catch(() => {}) }, [])
  useEffect(() => {
    if (!liveFeedEnabled) return
    const ws = createWebSocket((event) => {
      setLiveEvents((previous) => [event, ...previous].slice(0, 12))
      setPulseKey((previous) => previous + 1)
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['trend'] })
      queryClient.invalidateQueries({ queryKey: ['strategy-comparison'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
    })
    return () => ws.close()
  }, [liveFeedEnabled, queryClient])
  useEffect(() => {
    const timer = window.setTimeout(() => setAppliedThreshold(decisionThreshold), 180)
    return () => window.clearTimeout(timer)
  }, [decisionThreshold])

  async function toggleLiveFeed() {
    setLiveFeedPending(true)
    const next = !liveFeedEnabled
    try { await api.toggleLiveFeed(next); setLiveFeedEnabled(next); if (!next) setLiveEvents([]) } finally { setLiveFeedPending(false) }
  }

  return <div className="ledger-page">
    <header className="ledger-header">
      <div><p className="eyebrow">Payment recovery intelligence / daily statement</p><h1>Know when to bring the pulse back.</h1><p className="lede">RecoverAI treats every failed payment as a business decision, not an automatic retry.</p><p className="merchant-note">Retry windows and channel choice adapt by merchant type; subscription businesses benefit from billing-cycle timing.</p></div>
      <div className="header-actions"><div className="filter-wrap"><span>Retry economics shift by business type</span><select value={merchantType} onChange={(event) => setMerchantType(event.target.value)} aria-label="Merchant type"><option value="">All merchant types</option><option value="ecommerce">Ecommerce</option><option value="subscription_saas">Subscription SaaS</option><option value="edtech">Edtech</option><option value="food_delivery">Food delivery</option></select></div><button className={`feed-control ${liveFeedEnabled ? 'is-live' : ''}`} onClick={toggleLiveFeed} disabled={liveFeedPending}><Radio size={15} /> {liveFeedPending ? 'Connecting...' : liveFeedEnabled ? 'Live traffic on' : 'Simulate live traffic'}</button></div>
    </header>

    <section className="pulse-section" aria-label="Payment pulse">
      <div className="pulse-copy"><p className="eyebrow">Portfolio pulse</p><div className="pulse-number">{summaryLoading ? '...' : formatPercent(summary?.recovery_rate ?? 0)}</div><p>recovery rate across {summary?.total_transactions ?? 0} transactions</p><div className="essential-metrics"><Metric label="Net revenue impact" value={formatCurrency(strategy?.recoverai.net_gain ?? 0)} positive /><Metric label="Failed payments" value={String(summary?.failed_count ?? 0)} /><Metric label="Recovered" value={String(summary?.recovered_count ?? 0)} positive /></div></div>
      <PulseLine pulseKey={pulseKey} />
    </section>

    <section className="statement-section comparison-section">
      <div className="section-heading"><div><p className="eyebrow">Decision ledger</p><h2>Naive vs RecoverAI</h2></div><p className="section-note">A flat ₹{strategy?.retry_cost_per_attempt ?? 2} mock retry cost per failed payment.</p></div>
      <div className="delta-callout"><span>RecoverAI net advantage</span><strong>{strategyLoading ? '...' : `+${formatCurrency(strategy?.net_gain_difference ?? 0)}`}</strong><small>by knowing which payments to skip</small></div>
      <div className="strategy-ledger"><StrategyColumn label="Naive strategy" caption="Retry everything" metrics={strategy?.naive} loading={strategyLoading} /><StrategyColumn label="RecoverAI strategy" caption="Retry positive expected-value cases" metrics={strategy?.recoverai} loading={strategyLoading} featured /></div>
      <div className="decision-lab"><div><p className="eyebrow">Decision lab</p><strong>Minimum net value to retry: ₹{decisionThreshold}</strong><p>Adjust the minimum expected value RecoverAI requires before recommending a retry, then watch the strategy adapt.</p>{strategyFetching && <small className="lab-status">Recalculating decision ledger...</small>}{!strategyFetching && strategy?.recoverai.retry_costs === 0 && <small className="lab-status">No transactions currently meet this retry threshold.</small>}</div><input type="range" min="0" max="50" step="1" value={decisionThreshold} onChange={(event) => setDecisionThreshold(Number(event.target.value))} aria-label="Minimum expected value to retry" /></div>
      <div className="ab-validation"><span>5-batch validation: RecoverAI won {abValidation?.winning_batches ?? 0} of 5 batches, average advantage {formatCurrency(abValidation?.average_advantage ?? 0)}.</span><div>{abValidation?.batches.map((batch) => <span className={batch.recoverai_wins ? 'positive-ink' : 'negative-ink'} key={batch.batch}>Batch {batch.batch}: {batch.net_gain_difference >= 0 ? '+' : ''}{formatCurrency(batch.net_gain_difference)}</span>)}</div></div>
    </section>

    <div className="support-grid">
      <section className="statement-section trend-section"><div className="section-heading"><div><p className="eyebrow">Signal history</p><h2>Recovery trend</h2></div></div>{trendLoading ? <div className="ledger-loading" /> : trend?.length ? <TrendLine points={trend} /> : <p className="empty-copy">No recovery activity in the statement window.</p>}</section>
      <section className="statement-section live-section"><div className="section-heading"><div><p className="eyebrow">Receipt printer</p><h2>Live feed</h2></div><Activity size={17} /></div><div className="ticker-list"><AnimatePresence initial={false}>{liveEvents.length ? liveEvents.map((event, index) => <LiveReceipt event={event} key={`${event.transaction_id}-${event.timestamp}-${index}`} />) : <p className="empty-copy">{liveFeedEnabled ? 'Waiting for the next payment pulse...' : 'Turn on live traffic to print new events.'}</p>}</AnimatePresence></div></section>
    </div>

    <section className="statement-section breakdown-section"><div className="section-heading"><div><p className="eyebrow">Failure ledger</p><h2>What is stopping payment?</h2></div></div><div className="breakdown-list">{breakdown?.map((item) => <div className="breakdown-row" key={item.reason}><span>{formatReason(item.reason)}</span><div className="bar-track"><i style={{ width: `${item.percentage}%` }} /></div><strong>{item.count}</strong></div>)}</div></section>
  </div>
}

function Metric({ label, value, positive = false }: { label: string; value: string; positive?: boolean }) { return <div className="essential-metric"><span>{label}</span><strong className={positive ? 'positive-ink' : ''}>{value}</strong></div> }
function StrategyColumn({ label, caption, metrics, loading, featured = false }: { label: string; caption: string; metrics?: StrategyMetrics; loading: boolean; featured?: boolean }) { return <div className={`strategy-column ${featured ? 'featured' : ''}`}><div className="strategy-title"><div><h3>{label}</h3><p>{caption}</p></div>{featured ? <ArrowUpRight className="positive-ink" size={19} /> : <ArrowDownRight className="negative-ink" size={19} />}</div><LedgerMetric label="Recovered revenue" value={metrics?.recovered_revenue} loading={loading} /><LedgerMetric label="Retry costs" value={metrics?.retry_costs} loading={loading} negative /><LedgerMetric label="Net gain" value={metrics?.net_gain} loading={loading} emphasized={featured} /></div> }
function LedgerMetric({ label, value, loading, negative = false, emphasized = false }: { label: string; value?: number; loading: boolean; negative?: boolean; emphasized?: boolean }) { return <div className={`ledger-metric ${emphasized ? 'emphasized' : ''}`}><span>{label}</span><strong className={negative ? 'negative-ink' : ''}>{loading ? '...' : formatCurrency(value ?? 0)}</strong></div> }
function PulseLine({ pulseKey }: { pulseKey: number }) { return <div className={`pulse-visual ${pulseKey ? 'pulse-is-active' : ''}`} key={pulseKey}><svg viewBox="0 0 720 190" role="img" aria-label="Payment pulse showing failed and recovered transaction signals"><path className="pulse-grid" d="M0 95H720" /><path className="pulse-path" d="M0 95H105L122 95L132 142L143 42L154 95H250L267 95L279 130L290 58L301 95H398L412 95L424 150L437 34L450 95H535L550 95L560 120L572 70L585 95H720" /></svg><div className="pulse-legend"><span><i className="pulse-mark failed-mark" /> failed / flatline dip</span><span><i className="pulse-mark recovered-mark" /> recovered / pulse restored</span></div></div> }
function TrendLine({ points }: { points: Array<{ date: string; recovery_rate: number }> }) { const max = Math.max(...points.map((point) => point.recovery_rate), 1); const width = 700; const height = 190; const path = points.map((point, index) => `${index ? 'L' : 'M'} ${(index / Math.max(points.length - 1, 1)) * width} ${height - (point.recovery_rate / max) * 150 - 15}`).join(' '); return <div className="trend-wrap"><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"><path className="trend-baseline" d={`M0 ${height - 15}H${width}`} /><path className="trend-path" d={path} /></svg><div className="trend-labels"><span>{points[0]?.date}</span><span>{points[points.length - 1]?.date}</span></div></div> }
function LiveReceipt({ event }: { event: LiveEvent }) { const status = String(event.data?.status || 'event'); return <motion.div className="receipt-row" initial={{ opacity: 0, x: -18 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 18 }}><span className={status === 'captured' ? 'positive-ink' : 'negative-ink'}>{status === 'captured' ? <Check size={15} /> : <X size={15} />}</span><div><strong>{String(event.data?.razorpay_payment_id || `TX #${event.transaction_id}`)}</strong><small>{status} / {formatCurrency(Number(event.data?.amount || 0))}</small></div><time>{new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></motion.div> }
