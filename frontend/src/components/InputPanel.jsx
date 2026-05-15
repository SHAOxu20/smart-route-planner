import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Mic, MicOff, MapPin, Navigation, Loader2 } from 'lucide-react'

const QUICK_PROMPTS = [
  { label: '💑 约会', text: '周末和女朋友约会，想去有氛围感的地方，拍照好看，不要太贵' },
  { label: '👨‍👩‍👧 亲子', text: '带5岁小朋友出去玩一天，最好能学点东西，室内为主' },
  { label: '🍜 美食', text: '想吃地道本地菜，环境要好，适合请朋友吃饭' },
  { label: '☕ 休闲', text: '想找个安静的地方喝咖啡看书，然后逛逛有意思的小店' },
]

export default function InputPanel({ onPlan, loading, onVoiceInput, userLocation, setUserLocation }) {
  const [query, setQuery] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [city, setCity] = useState(userLocation?.city || '')
  const [locating, setLocating] = useState(!userLocation)
  const [locError, setLocError] = useState('')
  const recognitionRef = useRef(null)
  const locatingRef = useRef(false)

  // 同步外部 city 更新
  useEffect(() => {
    if (userLocation?.city) setCity(userLocation.city)
  }, [userLocation?.city])

  // 首次加载自动定位
  useEffect(() => {
    if (!userLocation && !locatingRef.current) {
      detectLocation()
    }
  }, [])

  const resolveCity = useCallback(async (lat, lng) => {
    try {
      const resp = await fetch(
        `https://restapi.amap.com/v3/geocode/regeo?key=316109962e9cad4e001c053ba0841ba0&location=${lng},${lat}`
      )
      const data = await resp.json()
      if (data.status === '1' && data.regeocode) {
        const addr = data.regeocode.addressComponent
        const detectedCity = addr.city || addr.province || ''
        if (detectedCity) {
          return detectedCity.replace(/市$/, '')
        }
      }
    } catch {}
    return ''
  }, [])

  const onLocationSuccess = useCallback(async (lat, lng, cityName) => {
    const resolvedCity = cityName || await resolveCity(lat, lng)
    setUserLocation({ lat, lng, city: resolvedCity, ts: Date.now() })
    // 缓存 5 分钟
    try { localStorage.setItem('last_location', JSON.stringify({ lat, lng, city: resolvedCity, ts: Date.now() })) } catch {}
    setLocating(false)
    setLocError('')
  }, [setUserLocation, resolveCity])

  const detectLocation = useCallback(() => {
    if (locatingRef.current) return
    locatingRef.current = true
    setLocating(true)
    setLocError('')

    // 先用缓存（5分钟内）
    try {
      const cached = JSON.parse(localStorage.getItem('last_location') || 'null')
      if (cached && cached.lat && Date.now() - cached.ts < 300000) {
        setUserLocation({ lat: cached.lat, lng: cached.lng, city: cached.city, ts: cached.ts })
        setCity(cached.city)
        setLocating(false)
        locatingRef.current = false
        return
      }
    } catch {}

    // 方案0: IP 定位 — 无需权限，毫秒级（桌面首选）
    fetch('https://ipapi.co/json/')
      .then(r => r.json())
      .then(data => {
        if (data.latitude && data.longitude) {
          const cityName = (data.city || '').replace(/市$/, '')
          onLocationSuccess(data.latitude, data.longitude, cityName)
        }
      })
      .catch(() => {})

    // 方案1: 浏览器定位 — 手机 < 1 秒 (并行)
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => onLocationSuccess(pos.coords.latitude, pos.coords.longitude, userLocation?.city || ''),
        () => {},
        { enableHighAccuracy: false, timeout: 5000, maximumAge: 120000 }
      )
    }

    // 方案2: 高德定位 — 国产手机 GNSS/BDS 精度更高 (并行)
    if (window.AMap && window.AMap.Geolocation) {
      new window.AMap.Geolocation({
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 120000,
        convert: true,
        showButton: false,
        showMarker: false,
        showCircle: false,
      }).getCurrentPosition((status, result) => {
        if (status === 'complete' && result.position) {
          onLocationSuccess(result.position.lat, result.position.lng, userLocation?.city || '')
        }
      })
    }

    // 兜底超时
    setTimeout(() => {
      if (!userLocation) {
        setLocating(false)
        setLocError('定位失败，请检查权限后重试')
      }
      locatingRef.current = false
    }, 6000)
  }, [setUserLocation, onLocationSuccess, userLocation])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!query.trim() || loading || !city) return
    onPlan(query.trim(), city)
  }

  const toggleVoice = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('你的浏览器不支持语音输入，请使用 Chrome')
      return
    }

    if (isRecording) {
      recognitionRef.current?.stop()
      setIsRecording(false)
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = 'zh-CN'
    recognition.interimResults = true
    recognition.continuous = false

    recognition.onresult = (event) => {
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        final += event.results[i][0].transcript
      }
      if (event.results[0]?.isFinal) {
        setQuery(final)
        setIsRecording(false)
        if (final.trim()) onVoiceInput(final)
      }
    }

    recognition.onerror = () => setIsRecording(false)
    recognition.onend = () => setIsRecording(false)

    recognitionRef.current = recognition
    recognition.start()
    setIsRecording(true)
  }, [isRecording, onVoiceInput])

  return (
    <div className="glass-card p-4">
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* 定位 + 城市行 */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* GPS 定位按钮 */}
          <button
            type="button"
            onClick={detectLocation}
            disabled={locating}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              userLocation
                ? 'bg-green-50 text-green-600 border border-green-200'
                : 'bg-blue-50 text-blue-600 border border-blue-200'
            }`}
          >
            {locating ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Navigation size={13} />
            )}
            {userLocation ? '已定位' : locating ? '定位中...' : '定位'}
          </button>

          {/* 城市 */}
          <div className="flex items-center gap-1 text-sm text-gray-500">
            <MapPin size={14} />
            {city ? (
              <span className="text-gray-700 font-medium">{city}</span>
            ) : (
              <span className="text-gray-400 animate-pulse">获取中...</span>
            )}
          </div>

          {/* 坐标显示 */}
          {userLocation && (
            <span className="text-[10px] text-gray-400 ml-auto">
              {userLocation.lat.toFixed(4)}, {userLocation.lng.toFixed(4)}
            </span>
          )}
        </div>

        {/* 定位错误 */}
        {locError && (
          <div className="text-xs text-orange-500 flex items-center gap-1">
            <span>⚠️</span> {locError}
            <button type="button" onClick={detectLocation} className="underline ml-1">重试</button>
          </div>
        )}

        {/* 输入框 */}
        <div className="relative">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="描述你的出行需求..."
            className="input-field min-h-[90px] resize-none pr-12 text-base"
            rows={3}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e)
              }
            }}
            disabled={loading}
          />
          <button
            type="button"
            onClick={toggleVoice}
            className={`absolute right-3 bottom-3 w-10 h-10 rounded-full flex items-center justify-center transition-all ${
              isRecording
                ? 'bg-red-500 text-white pulse-recording'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200 active:bg-gray-300'
            }`}
            title={isRecording ? '点击停止录音' : '语音输入'}
          >
            {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
        </div>

        {isRecording && (
          <div className="flex items-center gap-2 text-sm text-red-500 animate-pulse">
            <div className="w-2 h-2 bg-red-500 rounded-full" />
            正在聆听...点击麦克风停止
          </div>
        )}

        {/* 快捷提示 */}
        <div className="flex flex-wrap gap-1.5">
          {QUICK_PROMPTS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => {
                if (!city) return
                setQuery(p.text)
                onPlan(p.text, city)
              }}
              disabled={loading || !city}
              className="px-3 py-2 bg-gray-50 hover:bg-blue-50 border border-gray-100 hover:border-blue-200
                         rounded-xl text-xs text-gray-600 hover:text-blue-600 transition-all disabled:opacity-50"
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* 提交 */}
        <button
          type="submit"
          disabled={loading || !query.trim() || !city}
          className="btn-primary w-full flex items-center justify-center gap-2 text-base py-4"
        >
          <Send size={18} />
          {loading ? '规划中...' : !city ? '请先获取定位' : '生成路线'}
        </button>
      </form>
    </div>
  )
}
