const CACHE = "shasthopath-v12";
const CORE = [
  "./", "index.html", "download.html", "styles.css", "directory.css", "app-download.css", "app.js", "manifest.webmanifest",
  "icon.svg", "tile-fallback.svg", "vendor/leaflet/leaflet.css",
  "vendor/leaflet/leaflet.js", "data/catalog.json", "data/national.json", "data/dhaka.json", "data/bandarban.json"
];

self.addEventListener("install", event => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)));
});

self.addEventListener("activate", event => event.waitUntil(Promise.all([
  caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))),
  self.clients.claim()
])));

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const requestUrl = new URL(event.request.url);
  if (requestUrl.pathname.startsWith("/api/")) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    if (!requestUrl.hostname.endsWith("basemaps.cartocdn.com") && (response.ok || response.type === "opaque")) {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => event.request.destination === "image" ? caches.match("tile-fallback.svg") : caches.match("index.html"))));
});
