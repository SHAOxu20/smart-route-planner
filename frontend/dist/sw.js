const CACHE = 'route-planner-v3'

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(['/manifest.json', '/icon-192.png', '/icon-512.png']))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    ))
  )
  self.clients.claim()
})

self.addEventListener('fetch', (e) => {
  // 对 HTML 永远走网络（确保拿到最新 JS 引用）
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/')))
    return
  }
  // JS/CSS/图片走缓存兜底
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        if (resp.ok) {
          const clone = resp.clone()
          caches.open(CACHE).then(c => c.put(e.request, clone))
        }
        return resp
      })
      .catch(() => caches.match(e.request))
  )
})
