import { useState, useEffect } from 'react'
import { History, Clock, ChevronRight, RefreshCw } from 'lucide-react'

export default function HistoryPanel({ sessionId, onSelect }) {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    fetch(`/api/history/${sessionId}`)
      .then(r => r.json())
      .then(data => {
        setRecords(Array.isArray(data) ? data : [])
      })
      .catch(() => setRecords([]))
      .finally(() => setLoading(false))
  }, [sessionId])

  if (records.length === 0 && !loading) {
    return (
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
          <History size={15} />
          历史记录
        </div>
        <p className="text-xs text-gray-400">尚无历史记录，开始规划你的第一条路线吧</p>
      </div>
    )
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
        <History size={15} />
        历史记录
        <span className="text-xs text-gray-400">({records.length})</span>
        {loading && (
          <RefreshCw size={12} className="animate-spin text-gray-400" />
        )}
      </div>

      <div className="space-y-2 max-h-[300px] overflow-y-auto">
        {records.map((r, i) => {
          const intent = typeof r.parsed_intent === 'string'
            ? JSON.parse(r.parsed_intent || '{}')
            : r.parsed_intent || {}

          return (
            <button
              key={r.id}
              onClick={() => onSelect(r.query_text)}
              className="w-full text-left p-3 bg-gray-50 hover:bg-blue-50 rounded-xl transition-all group"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 truncate font-medium">
                    {r.query_text}
                  </p>
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <Clock size={11} />
                      {r.created_at ? new Date(r.created_at).toLocaleDateString('zh-CN') : ''}
                    </span>
                    {intent.purpose && (
                      <span className="px-1.5 py-0.5 bg-white rounded text-gray-500">
                        {intent.purpose}
                      </span>
                    )}
                    {intent.budget && (
                      <span>¥{intent.budget}</span>
                    )}
                    {r.feedback && (
                      <span className="text-orange-400">[{r.feedback}]</span>
                    )}
                  </div>
                </div>
                <ChevronRight size={14} className="text-gray-300 group-hover:text-blue-400 transition-colors shrink-0" />
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
