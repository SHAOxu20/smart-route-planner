import { useState } from 'react'
import { MapPin, Clock, Wallet, Star, TrendingUp, ArrowRight, MessageSquare } from 'lucide-react'

const PLAN_KEYS = { plan_a: 'A', plan_b: 'B', plan_c: 'C' }
const PLAN_COLORS = {
  plan_a: 'from-blue-500 to-cyan-500',
  plan_b: 'from-emerald-500 to-teal-500',
  plan_c: 'from-orange-500 to-amber-500',
}

export default function RouteDisplay({ plans, intent, weather, activePlan, onPlanChange, onAdjust }) {
  const [adjustInput, setAdjustInput] = useState('')
  const [polishing, setPolishing] = useState(false)
  const plan = plans?.[activePlan]

  if (!plan) return null

  const handleAdjust = () => {
    if (!adjustInput.trim()) return
    onAdjust(adjustInput.trim())
    setAdjustInput('')
  }

  const handleAIPolish = async () => {
    setPolishing(true)
    try {
      const res = await fetch('/api/route/describe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan, intent, weather }),
      })
      const data = await res.json()
      if (data.description) {
        plan.description = data.description
        // Force re-render
        setPolishing(false)
      }
    } catch { setPolishing(false) }
  }

  return (
    <div className="space-y-4">
      {/* Plan Tabs */}
      <div className="flex gap-2">
        {Object.entries(PLAN_KEYS).map(([key, label]) => {
          const isActive = key === activePlan
          const p = plans?.[key]
          return (
            <button
              key={key}
              onClick={() => onPlanChange(key)}
              className={`flex-1 p-4 rounded-xl border-2 transition-all text-left ${
                isActive
                  ? `border-transparent bg-gradient-to-r ${PLAN_COLORS[key]} text-white shadow-lg`
                  : 'border-gray-100 bg-white hover:border-gray-200'
              }`}
            >
              <div className={`text-xs font-bold mb-1 ${isActive ? 'text-white/80' : 'text-gray-400'}`}>
                方案 {label}
              </div>
              <div className={`text-sm font-semibold ${isActive ? 'text-white' : 'text-gray-700'}`}>
                {p?.label || '—'}
              </div>
              <div className={`text-xs mt-1 ${isActive ? 'text-white/70' : 'text-gray-400'}`}>
                {p?.poi_count || 0} 站 · ¥{p?.total_cost || 0} · {p?.total_time_minutes || 0}min
              </div>
            </button>
          )
        })}
      </div>

      {/* Weather Advice */}
      {weather?.constraints?.advice && (
        <div className="p-3 bg-blue-50 border border-blue-100 rounded-xl text-sm text-blue-700 flex items-center gap-2">
          <span className="text-base">🌤️</span>
          {weather.constraints.advice}
        </div>
      )}

      {/* Route Description */}
      {plan.description && (
        <div className="glass-card p-4">
          <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
            {plan.description}
          </div>
          <button
            onClick={handleAIPolish}
            disabled={polishing}
            className="mt-3 flex items-center gap-1.5 text-xs text-primary-500 hover:text-primary-600 font-medium disabled:opacity-50"
          >
            {polishing ? (
              <><div className="w-3 h-3 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" /> AI 润色中...</>
            ) : (
              '✨ AI 润色'
            )}
          </button>
        </div>
      )}

      {/* Route Timeline */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-gray-500 mb-4 flex items-center gap-2">
          <Clock size={15} />
          路线时间线 · {plan.label}
        </h3>

        <div className="space-y-0">
          {plan.stops?.map((stop, idx) => (
            <div key={idx} className="relative flex gap-4 pb-5">
              {/* Timeline line */}
              {idx < plan.stops.length - 1 && (
                <div className="absolute left-[17px] top-10 bottom-0 w-0.5 bg-gray-200" />
              )}

              {/* Dot */}
              <div className={`shrink-0 w-[35px] h-[35px] rounded-xl bg-gradient-to-br ${PLAN_COLORS[activePlan]} flex items-center justify-center text-white text-xs font-bold shadow-md z-10`}>
                {idx + 1}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-gray-800">{stop.name}</span>
                  <span className="text-xs px-2 py-0.5 bg-gray-100 rounded-full text-gray-500">
                    {stop.category}
                  </span>
                </div>

                <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400 flex-wrap">
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> {stop.arrival_time}
                  </span>
                  <span className="flex items-center gap-1">
                    <Wallet size={12} /> ¥{stop.cost}/人
                  </span>
                  <span className="flex items-center gap-1">
                    <Star size={12} className="text-amber-400" /> {stop.rating}
                  </span>
                </div>

                {/* Tags */}
                {stop.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {stop.tags.slice(0, 4).map((tag, ti) => (
                      <span key={ti} className="text-[11px] px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {stop.ugc_summary && (
                  <p className="text-xs text-gray-400 mt-1.5 italic line-clamp-1">
                    "{stop.ugc_summary}"
                  </p>
                )}

                {/* Connection */}
                {idx < plan.stops.length - 1 && (
                  <div className="flex items-center gap-1 mt-2 text-xs text-gray-400">
                    <ArrowRight size={11} />
                    {stop.travel_from_prev}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="flex items-center gap-4 pt-3 border-t border-gray-100 text-sm">
          <div className="flex items-center gap-1 text-gray-600">
            <Wallet size={15} />
            <span className="font-semibold">总预算 ¥{plan.total_cost}</span>
          </div>
          <div className="flex items-center gap-1 text-gray-600">
            <Clock size={15} />
            <span className="font-semibold">{plan.total_time_minutes} 分钟</span>
          </div>
          <div className="flex items-center gap-1 text-gray-600">
            <MapPin size={15} />
            <span className="font-semibold">{plan.poi_count} 站</span>
          </div>
        </div>
      </div>

      {/* Dynamic Adjust */}
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
          <MessageSquare size={15} />
          动态调整
        </div>
        <div className="flex gap-2 mb-3 flex-wrap">
          {['太贵了', '加个甜品店', '时间来不及了', '有室内吗', '换人少的'].map((fb) => (
            <button
              key={fb}
              onClick={() => onAdjust(fb)}
              className="px-3 py-1.5 bg-gray-50 hover:bg-blue-50 border border-gray-100 hover:border-blue-200
                         rounded-lg text-xs text-gray-600 hover:text-blue-600 transition-all"
            >
              {fb}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={adjustInput}
            onChange={(e) => setAdjustInput(e.target.value)}
            placeholder="输入调整需求..."
            className="input-field flex-1 text-sm py-2"
            onKeyDown={(e) => e.key === 'Enter' && handleAdjust()}
          />
          <button onClick={handleAdjust} className="btn-primary text-sm py-2 px-4">
            调整
          </button>
        </div>
      </div>
    </div>
  )
}
