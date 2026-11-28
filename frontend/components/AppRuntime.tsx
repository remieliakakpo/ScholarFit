"use client";
import { useEffect, useState } from "react";
import { applyLite, isLite, liteChoice, setLite, slowConnection } from "@/lib/pwa";
import Icon from "./Icon";
import { useT } from "./LangProvider";

/** Service worker (production), bandeau hors connexion et notification du mode léger. */
export default function AppRuntime() {
  const { t } = useT();
  const [offline, setOffline] = useState(false);
  const [liteNotice, setLiteNotice] = useState(false);

  useEffect(() => {
    const enabled = process.env.NODE_ENV === "production" || process.env.NEXT_PUBLIC_ENABLE_SW === "1";
    if (enabled && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    // Mode léger automatique : activé dès qu'une connexion lente est détectée, puis une
    // notification le dit et laisse choisir. Le choix est retenu : elle ne revient plus.
    const checkLite = () => {
      applyLite();
      setLiteNotice(liteChoice() === null && slowConnection());
    };
    checkLite();
    const c = (navigator as Navigator & { connection?: EventTarget }).connection;
    c?.addEventListener?.("change", checkLite);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
      c?.removeEventListener?.("change", checkLite);
    };
  }, []);

  function choose(keep: boolean) {
    setLite(keep);
    setLiteNotice(false);
  }

  return (
    <>
      {liteNotice && (
        <div role="dialog" aria-live="polite" aria-labelledby="lite-title"
          className={`fixed inset-x-3 z-50 mx-auto max-w-md rounded-2xl border border-line bg-card p-4 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)] sm:left-auto sm:right-4 sm:mx-0 ${offline ? "bottom-14" : "bottom-4"}`}>
          <div className="flex gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-soft text-brand"><Icon name="feather" className="h-4 w-4" /></span>
            <div className="min-w-0 flex-1">
              <p id="lite-title" className="text-sm font-semibold">{t("Connexion lente : mode léger activé")}</p>
              <p className="mt-1 text-xs text-muted">{t("Le globe animé, les illustrations et les animations sont masqués pour que le site se charge plus vite et consomme moins de données.")}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="btn-primary px-4 py-1.5 text-xs" onClick={() => choose(true)}>{t("Garder le mode léger")}</button>
                <button type="button" className="btn-ghost px-4 py-1.5 text-xs" onClick={() => choose(false)}>{t("Tout afficher")}</button>
              </div>
            </div>
          </div>
        </div>
      )}
      {offline && (
        <div role="status" className="fixed inset-x-0 bottom-0 z-50 flex items-center justify-center gap-2 bg-gold px-4 py-2 text-center text-sm font-medium text-[#1a1200]">
          <Icon name="offline" className="h-4 w-4" />
          {t("Hors connexion : vous voyez la dernière version enregistrée sur cet appareil.")}
        </div>
      )}
    </>
  );
}

/** Mode léger : sans globe animé ni illustrations, pour les connexions lentes. */
export function useLite(): boolean {
  const [lite, setL] = useState(false);
  useEffect(() => {
    const sync = () => setL(isLite());
    sync();
    window.addEventListener("lite-change", sync);
    return () => window.removeEventListener("lite-change", sync);
  }, []);
  return lite;
}

/** Lien discret (pied de page) pour changer d'avis après la notification. */
export function LiteLink() {
  const { t } = useT();
  const lite = useLite();
  return (
    <button type="button" onClick={() => setLite(!lite)} className="inline-flex items-center gap-1 hover:text-ink hover:underline">
      <Icon name="feather" className="h-3.5 w-3.5" />
      {lite ? t("Mode léger activé · tout afficher") : t("Passer en mode léger")}
    </button>
  );
}
