/* ScholarFit : service worker (application installable et lecture hors ligne).
 *
 * - Fichiers du site (/_next/static, icônes) : gardés en cache, servis tout de suite.
 * - Pages : réseau d'abord ; sans réseau, la dernière version vue de la page, sinon /hors-ligne.
 * - Données (fiches, suivi, alertes) : réseau d'abord ; sans réseau, la dernière réponse gardée.
 *   Jamais gardé : comptes, export des données, paiements, calendriers, administration.
 * - À la déconnexion, le site demande d'effacer les pages et données gardées (message "clear").
 */
const VERSION = "v1";
const STATIC = `sf-static-${VERSION}`;
const PAGES = `sf-pages-${VERSION}`;
const DATA = `sf-data-${VERSION}`;
const OFFLINE = "/hors-ligne";
const PRECACHE = [OFFLINE, "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

// Données utiles hors ligne (GET seulement)
const DATA_OK = [/^\/api\/scholarships\/\d+$/, /^\/api\/applications$/, /^\/api\/alerts$/, /^\/api\/meta$/, /^\/api\/matches/, /^\/api\/recherches$/];
// Pages gardées pour la lecture hors ligne
const PAGE_OK = [/^\/$/, /^\/bourses\/\d+$/, /^\/mes-bourses$/, /^\/suivi$/, /^\/bourses$/];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(STATIC).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("sf-") && !k.endsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  const msg = event.data || {};
  if (msg.type === "clear") {
    event.waitUntil(Promise.all([caches.delete(PAGES), caches.delete(DATA)]));
  } else if (msg.type === "warm" && Array.isArray(msg.urls)) {
    // Fiches suivies : gardées pour être lisibles sans réseau (page + données)
    event.waitUntil(warm(msg.urls.filter((u) => typeof u === "string" && u.startsWith("/bourses/")).slice(0, 40)));
  }
});

async function warm(paths) {
  const pages = await caches.open(PAGES);
  const data = await caches.open(DATA);
  await Promise.all(paths.map(async (p) => {
    try {
      const page = await fetch(p, { credentials: "same-origin" });
      if (page.ok) await pages.put(p, page);
      const id = p.split("/").pop();
      const api = await fetch(`/api/scholarships/${id}`, { credentials: "same-origin" });
      if (api.ok) await data.put(`/api/scholarships/${id}`, api);
    } catch {
      /* hors ligne : ce sera pour la prochaine fois */
    }
  }));
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/") || url.pathname.startsWith("/flags/") || url.pathname.startsWith("/brand/")) {
    event.respondWith(cacheFirst(req, STATIC));
    return;
  }
  if (url.pathname.startsWith("/api/")) {
    if (DATA_OK.some((r) => r.test(url.pathname))) event.respondWith(networkFirst(req, DATA, null));
    return; // le reste de l'API n'est jamais gardé
  }
  if (req.mode === "navigate") {
    const keep = PAGE_OK.some((r) => r.test(url.pathname));
    event.respondWith(networkFirst(req, keep ? PAGES : null, OFFLINE));
  }
});

async function cacheFirst(req, name) {
  const hit = await caches.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) (await caches.open(name)).put(req, res.clone());
  return res;
}

async function networkFirst(req, name, fallback) {
  try {
    const res = await fetch(req);
    // Une réponse privée (cookie de session) n'est gardée que sur cet appareil, et effacée à la déconnexion
    if (name && res.ok && res.type === "basic") (await caches.open(name)).put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await caches.match(req, { ignoreSearch: req.mode !== "navigate" ? false : true });
    if (hit) return hit;
    if (fallback) {
      const off = await caches.match(fallback);
      if (off) return off;
    }
    throw err;
  }
}
