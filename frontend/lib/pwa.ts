// Service worker (application installable, lecture hors ligne) et mode léger.

/** Demande au service worker de garder ces fiches pour les lire sans réseau. */
export function warmOffline(paths: string[]) {
  if (typeof navigator === "undefined" || !navigator.serviceWorker?.controller || paths.length === 0) return;
  navigator.serviceWorker.controller.postMessage({ type: "warm", urls: paths });
}

/** Efface les pages et données gardées sur l'appareil (appelé à la déconnexion). */
export function clearOfflineData() {
  if (typeof navigator === "undefined") return;
  navigator.serviceWorker?.controller?.postMessage({ type: "clear" });
  if (typeof caches !== "undefined") {
    caches.keys().then((keys) => keys.filter((k) => k.startsWith("sf-pages") || k.startsWith("sf-data")).forEach((k) => caches.delete(k))).catch(() => {});
  }
}

// ---------------------------------------------------------------- mode léger
const LITE_KEY = "sf_lite"; // "1" activé, "0" désactivé, absent = automatique selon la connexion

type NetInfo = { saveData?: boolean; effectiveType?: string };

/** Connexion lente ou « économiseur de données » du téléphone. */
export function slowConnection(): boolean {
  if (typeof navigator === "undefined") return false;
  const c = (navigator as Navigator & { connection?: NetInfo }).connection;
  return !!c && (c.saveData === true || ["slow-2g", "2g", "3g"].includes(c.effectiveType ?? ""));
}

export function liteChoice(): "1" | "0" | null {
  try {
    const v = localStorage.getItem(LITE_KEY);
    return v === "1" || v === "0" ? v : null;
  } catch {
    return null;
  }
}

export function isLite(): boolean {
  if (typeof window === "undefined") return false;
  const choice = liteChoice();
  return choice ? choice === "1" : slowConnection();
}

export function setLite(on: boolean) {
  try {
    localStorage.setItem(LITE_KEY, on ? "1" : "0");
  } catch {
    /* stockage bloqué : le choix vaut pour cette page */
  }
  applyLite();
}

/** Pose data-lite sur <html> (les styles et composants animés s'en servent) et prévient la page. */
export function applyLite() {
  if (typeof document === "undefined") return;
  if (isLite()) document.documentElement.dataset.lite = "1";
  else delete document.documentElement.dataset.lite;
  window.dispatchEvent(new Event("lite-change"));
}

// Script exécuté avant l'affichage : évite de charger le globe puis de le retirer
export const LITE_SCRIPT = `try{var v=localStorage.getItem("${LITE_KEY}"),c=navigator.connection;if(v==="1"||(v!=="0"&&c&&(c.saveData||/^(slow-2g|2g|3g)$/.test(c.effectiveType||""))))document.documentElement.dataset.lite="1"}catch(e){}`;
