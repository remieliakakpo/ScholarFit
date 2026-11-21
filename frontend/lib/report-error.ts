// Remonte une erreur d'affichage à l'API (journal du serveur, et Sentry s'il est configuré).
// Sans donnée personnelle : message, pile d'appels tronquée, adresse de la page sans paramètres.
export function reportError(error: Error & { digest?: string }) {
  try {
    const body = JSON.stringify({
      message: String(error?.message || error).slice(0, 1000),
      stack: error?.stack ? String(error.stack).slice(0, 4000) : null,
      url: `${window.location.origin}${window.location.pathname}`.slice(0, 500),
      digest: error?.digest ?? null,
    });
    fetch("/api/erreurs-site", {
      method: "POST", body, keepalive: true,
      headers: { "Content-Type": "application/json", "X-Requested-With": "ScholarFit" },
    }).catch(() => {});
  } catch {
    /* ne jamais provoquer une seconde erreur */
  }
}
