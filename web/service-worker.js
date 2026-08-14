const CACHE = "shasthopath-v14";
const CORE = [
  "./", "index.html", "download.html", "update.html", "styles.css", "directory.css", "app-download.css", "update.css", "app.js", "update.js", "manifest.webmanifest",
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
  if (requestUrl.pathname.endsWith("/app-version.json")) {
    event.respondWith(fetch(event.request, { cache: "no-store" }));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    if (!requestUrl.hostname.endsWith("basemaps.cartocdn.com") && (response.ok || response.type === "opaque")) {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => event.request.destination === "image" ? caches.match("tile-fallback.svg") : caches.match("index.html"))));
});
