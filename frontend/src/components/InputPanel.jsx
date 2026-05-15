import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Mic, MicOff, MapPin, Navigation, Loader2 } from 'lucide-react'

const EXAMPLE_PROMPTS = [
  '周末和朋友出去玩，想去有意思的地方',
  '附近有什么好吃的推荐？人均100左右',
  '想找个安静的地方待一下午',
  '第一次来这个城市，有什么必去的？',
  '晚上去哪逛比较好？不要太远',
  '推荐几个拍照好看的地方',
  '有没有本地人常去的宝藏小店',
  '带爸妈玩一天，不要太累的路线',
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

  // 记录已成功的定位源，防止低优先级覆盖高优先级
  const locationRef = useRef(null)
  // 缓存 resolveCity 的 promise，避免重复请求
  const cityPromiseRef = useRef(null)

  const applyLocation = useCallback((lat, lng, cityName, source) => {
    // 优先级: amap(2) > browser(1) > ip(0)
    const priority = { amap: 2, browser: 1, ip: 0 }[source] || 0
    const prev = locationRef.current
    if (prev && prev.priority >= priority && prev.lat) return

    locationRef.current = { lat, lng, priority }
    const loc = { lat, lng, city: cityName || '', ts: Date.now(), source }
    setUserLocation(loc)

    // 异步补城市名，不阻塞定位
    if (!cityName) {
      const key = `${lat.toFixed(4)},${lng.toFixed(4)}`
      if (!cityPromiseRef.current || cityPromiseRef.current.key !== key) {
        cityPromiseRef.current = { key, promise: resolveCity(lat, lng) }
      }
      cityPromiseRef.current.promise.then(c => {
        if (c) {
          setCity(c)
          setUserLocation(prev => prev ? { ...prev, city: c } : prev)
        }
      }).catch(() => {})
    } else {
      setCity(cityName)
    }

    try {
      localStorage.setItem('last_location', JSON.stringify({ lat, lng, city: cityName, ts: Date.now() }))
    } catch {}
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
        applyLocation(cached.lat, cached.lng, cached.city || '', 'browser')
        locatingRef.current = false
        return
      }
    } catch {}

    // IP 仅作城市名兜底（不触发「已定位」）
    fetch('https://ipapi.co/json/')
      .then(r => r.json())
      .then(data => {
        if (data.city && !locationRef.current?.lat) {
          const c = (data.city || '').replace(/市$/, '')
          setCity(prev => prev || c)
        }
      })
      .catch(() => {})

    // 浏览器 GPS
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => applyLocation(pos.coords.latitude, pos.coords.longitude, '', 'browser'),
        () => {},
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
      )
    }

    // 高德 GNSS/BDS
    if (window.AMap && window.AMap.Geolocation) {
      new window.AMap.Geolocation({
        enableHighAccuracy: true, timeout: 15000, maximumAge: 30000,
        convert: true,
        showButton: false, showMarker: false, showCircle: false,
      }).getCurrentPosition((status, result) => {
        if (status === 'complete' && result.position) {
          // AMap geolocation 自带城市信息
          const city = result.addressComponent?.city || ''
          applyLocation(result.position.lat, result.position.lng, city.replace(/市$/, ''), 'amap')
        }
      })
    }

    // 兜底超时
    setTimeout(() => {
      locatingRef.current = false
      if (!locationRef.current?.lat) {
        setLocating(false)
        if (!city) setLocError('定位较慢，请确认已开启定位权限并重试')
      }
    }, 15000)
  }, [applyLocation, city])

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

        {/* 示例输入 */}
        <div className="overflow-x-auto scrollbar-hide">
          <div className="flex gap-1.5 pb-1" style={{ minWidth: 'max-content' }}>
            {EXAMPLE_PROMPTS.map((text, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setQuery(text)}
                disabled={loading}
                className="shrink-0 px-3 py-1.5 bg-gray-50 hover:bg-blue-50 border border-gray-100 hover:border-blue-200
                           rounded-full text-xs text-gray-500 hover:text-blue-600 transition-all disabled:opacity-50 whitespace-nowrap"
              >
                {text}
              </button>
            ))}
          </div>
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
