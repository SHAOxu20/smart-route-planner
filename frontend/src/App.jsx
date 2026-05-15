import { useState, useCallback } from 'react'
import InputPanel from './components/InputPanel'
import RouteDisplay from './components/RouteDisplay'
import MapView from './components/MapView'
import HistoryPanel from './components/HistoryPanel'
import { MapPin, Compass, Clock, MessageSquare } from 'lucide-react'

const API_BASE = '/api'

const TABS = [
  { id: 'plan', label: '路线', icon: Compass },
  { id: 'map', label: '地图', icon: MapPin },
  { id: 'history', label: '历史', icon: Clock },
]

export default function App() {
  const [sessionId, setSessionId] = useState(localStorage.getItem('route_session') || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [activePlan, setActivePlan] = useState('plan_a')
  const [activeTab, setActiveTab] = useState('plan')
  const [error, setError] = useState('')
  const [userLocation, setUserLocation] = useState(null) // { lat, lng, city }

  const planRoute = useCallback(async (query, city) => {
    if (!city) return
    setLoading(true)
    setError('')
    try {
      const body = { query, session_id: sessionId, city }
      // 附上 GPS 坐标
      if (userLocation) {
        body.start_lat = userLocation.lat
        body.start_lng = userLocation.lng
      }
      const res = await fetch(`${API_BASE}/route/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error('规划失败')
      const data = await res.json()
      setSessionId(data.session_id)
      localStorage.setItem('route_session', data.session_id)
      setResult(data)
      setActivePlan('plan_a')
      setActiveTab('plan')
    } catch (e) {
      setError(e.message || '网络错误，请确认后端已启动')
    } finally {
      setLoading(false)
    }
  }, [sessionId, userLocation])

  const adjustRoute = useCallback(async (feedback) => {
    if (!result) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/route/adjust`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          feedback,
          current_plan: result.plans?.[activePlan],
        }),
      })
      if (!res.ok) throw new Error('调整失败')
      const data = await res.json()
      setResult(prev => ({ ...prev, plans: data.plans, weather: data.weather }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [result, activePlan, sessionId])

  const planStops = result?.plans?.[activePlan]?.stops || []
  const intent = result?.intent || {}
  const weather = result?.weather || {}

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-pink-50 pb-20">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-gray-100 safe-top">
        <div className="max-w-lg mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl flex items-center justify-center">
              <MapPin size={16} className="text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-800 leading-tight">LocalSmartRoute</h1>
              <p className="text-[10px] text-gray-400">{userLocation?.city || ''} · 智能路线规划</p>
            </div>
          </div>
          {result && (
            <div className="text-xs text-gray-400">
              {weather?.constraints?.temperature || '—'}°C
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-lg mx-auto px-4 pt-4 space-y-4">
        {/* Input Panel */}
        <InputPanel
          onPlan={planRoute}
          loading={loading}
          sessionId={sessionId}
          onVoiceInput={(text) => planRoute(text, userLocation?.city)}
          userLocation={userLocation}
          setUserLocation={setUserLocation}
        />

        {/* Error */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm"
               onClick={() => setError('')}>
            {error} <span className="text-red-400 ml-1">点此关闭</span>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="glass-card p-6 flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-[3px] border-primary-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-gray-500">正在规划路线...</span>
          </div>
        )}

        {/* Tab Content */}
        {result && !loading && (
          <>
            {activeTab === 'plan' && (
              <RouteDisplay
                plans={result.plans}
                intent={intent}
                weather={weather}
                activePlan={activePlan}
                onPlanChange={setActivePlan}
                onAdjust={adjustRoute}
              />
            )}
            {activeTab === 'map' && (
              <MapView stops={planStops} weather={weather} userLocation={userLocation} />
            )}
            {activeTab === 'history' && (
              <HistoryPanel
                sessionId={sessionId}
                onSelect={(q) => {
                  planRoute(q)
                  setActiveTab('plan')
                }}
              />
            )}
          </>
        )}
      </main>

      {/* Bottom Nav */}
      {result && (
        <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-gray-100 safe-bottom">
          <div className="max-w-lg mx-auto flex">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex-1 flex flex-col items-center py-2 gap-0.5 transition-colors ${
                  activeTab === id ? 'text-primary-500' : 'text-gray-400'
                }`}
              >
                <Icon size={20} />
                <span className="text-[10px] font-medium">{label}</span>
              </button>
            ))}
          </div>
        </nav>
      )}
    </div>
  )
}
