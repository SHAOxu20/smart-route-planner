import { useEffect, useRef } from 'react'
import { MapPin } from 'lucide-react'

export default function MapView({ stops, weather, userLocation }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return

    // 高德地图初始化
    const initMap = () => {
      const AMap = window.AMap
      if (!AMap) {
        renderPlaceholder()
        return
      }

      // 动态计算地图中心：优先用户位置 > 首个站点 > 北京
      let centerLng = 116.397, centerLat = 39.909
      if (userLocation?.lng && userLocation?.lat) {
        centerLng = userLocation.lng
        centerLat = userLocation.lat
      } else if (stops?.length > 0 && stops[0].lng && stops[0].lat) {
        centerLng = stops[0].lng
        centerLat = stops[0].lat
      }

      if (!mapRef.current) {
        mapRef.current = new AMap.Map(containerRef.current, {
          zoom: 13,
          center: [centerLng, centerLat],
          mapStyle: 'amap://styles/light',
          resizeEnable: true,
        })
      }

      const map = mapRef.current
      map.clearMap()

      if (!stops || stops.length === 0) {
        // 无站点时标注用户位置
        new AMap.Marker({
          position: [centerLng, centerLat],
          map,
          title: userLocation?.city || '当前位置',
        })
        map.setCenter([centerLng, centerLat])
        return
      }

      const markers = []
      const pathPoints = []

      stops.forEach((stop, idx) => {
        const pos = [stop.lng || 121.4737, stop.lat || 31.2304]
        pathPoints.push(pos)

        // Marker with label
        const markerContent = `<div style="
          background: linear-gradient(135deg, #3b82f6, #8b5cf6);
          color: white; width: 28px; height: 28px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          font-size: 13px; font-weight: bold; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
          border: 2px solid white;
        ">${idx + 1}</div>`

        const marker = new AMap.Marker({
          position: pos,
          content: markerContent,
          offset: new AMap.Pixel(-14, -14),
          title: stop.name,
          map,
        })

        // Info window
        marker.on('click', () => {
          const info = new AMap.InfoWindow({
            content: `<div style="padding: 8px 12px; font-size: 13px;">
              <b>${stop.name}</b><br/>
              <span style="color: #6b7280;">${stop.category} · ¥${stop.cost}/人 · ⭐${stop.rating}</span>
            </div>`,
            offset: new AMap.Pixel(0, -35),
          })
          info.open(map, marker.getPosition())
        })

        markers.push(marker)
      })

      // Draw polyline
      if (pathPoints.length > 1) {
        new AMap.Polyline({
          path: pathPoints,
          strokeColor: '#3b82f6',
          strokeWeight: 4,
          strokeStyle: 'dashed',
          strokeOpacity: 0.7,
          showDir: true,
          map,
        })
      }

      map.setFitView(null, true, [60, 60, 60, 60])
    }

    const renderPlaceholder = () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = `
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;
            background:linear-gradient(135deg,#f0f9ff,#fdf2f8);border-radius:16px;color:#9ca3af;gap:8px;">
            <div style="font-size:40px;">🗺️</div>
            <div style="font-size:13px;">地图预览</div>
            <div style="font-size:11px;">配置高德 Key 后可显示地图</div>
          </div>`
      }
    }

    // 等待 AMap 加载
    if (window.AMap) {
      initMap()
    } else {
      const timer = setTimeout(() => {
        if (window.AMap) initMap()
        else renderPlaceholder()
      }, 2000)
      renderPlaceholder()
      return () => clearTimeout(timer)
    }
  }, [stops, userLocation])

  return (
    <div className="glass-card overflow-hidden">
      <div className="p-3 border-b border-gray-100 flex items-center gap-2 text-sm text-gray-500">
        <MapPin size={15} />
        路线地图
        {stops.length > 0 && (
          <span className="text-xs text-gray-400">({stops.length} 个点位)</span>
        )}
      </div>
      <div ref={containerRef} className="w-full h-[50vh] min-h-[300px]" />
    </div>
  )
}
