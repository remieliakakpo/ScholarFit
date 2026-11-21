"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Icon, { Logo } from "./Icon";
import StudentsIllustration from "./StudentsIllustration";
import { api, setSignedIn } from "@/lib/api";
import { useT } from "@/components/LangProvider";

function strength(p: string) {
  if (p.length < 8) return 0;
  let n = 1;
  if (/[a-z]/.test(p) && /[A-Z]/.test(p)) n++;
  if (/\d/.test(p)) n++;
  if (/[^A-Za-z0-9]/.test(p) || p.length >= 14) n++;
  return Math.min(n, 4);
}

/** Mot de passe aléatoire lisible (le navigateur proposera de l'enregistrer). */
function suggestPassword() {
  const sets = ["abcdefghjkmnpqrstuvwxyz", "ABCDEFGHJKMNPQRSTUVWXYZ", "23456789", "-_!?*#"];
  const r = new Uint32Array(16);
  crypto.getRandomValues(r);
  return Array.from(r, (v, i) => { const set = sets[i % 4 === 3 && i % 8 === 7 ? 3 : i % 3]; return set[v % set.length]; }).join("");
}

export type AuthMode = "connexion" | "inscription";

/** Page où revenir après connexion : seulement une page de ce site. « //autre.site » ou « /\autre.site »
 *  (que les navigateurs lisent comme une autre adresse) sont refusés, ce qui évite qu'un lien piégé
 *  vers /connexion?next=… renvoie la personne, une fois connectée, vers un faux site. */
function safeNext(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return null;
  try {
    const u = new URL(next, window.location.origin);
    return u.origin === window.location.origin ? u.pathname + u.search + u.hash : null;
  } catch {
    return null;
  }
}

// Les comptes de démo n'existent qu'en développement (APP_ENV=dev côté API) : identifiants masqués en production.
const SHOW_DEMO = process.env.NODE_ENV !== "production";

/** Fenêtre de connexion / inscription : illustration à gauche, champs à droite. */
export default function AuthPanel({ initialMode = "connexion", next, onClose, onSuccess }: { initialMode?: AuthMode; next?: string | null; onClose?: () => void; onSuccess?: () => void }) {
  const { t } = useT();
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);
  const [taken, setTaken] = useState(false);

  async function checkEmail() {
    if (mode !== "inscription" || !/^\S+@\S+\.\S+$/.test(email)) return setTaken(false);
    try {
      const r = await api<{ available: boolean }>(`/api/auth/email-disponible?email=${encodeURIComponent(email)}`);
      setTaken(!r.available);
    } catch { setTaken(false); }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const path = mode === "connexion" ? "/api/auth/login" : "/api/auth/register";
      const body = mode === "connexion" ? { email, password } : { email, password, accept_terms: consent };
      await api(path, { method: "POST", body: JSON.stringify(body) }); // l'API pose le cookie de session
      setSignedIn(true);
      const safe = safeNext(next);
      onSuccess?.();
      router.push(safe ?? (mode === "inscription" ? "/profil" : "/mes-bourses"));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "connexion";
  return (
    <div className="relative grid w-full max-w-4xl overflow-hidden rounded-3xl border border-line bg-card shadow-[0_40px_120px_-30px_rgba(0,0,0,0.7)] md:grid-cols-[1fr_1.1fr]">
      {onClose && (
        <button type="button" onClick={onClose} aria-label={t("Fermer")} className="absolute right-3 top-3 z-10 grid h-9 w-9 place-items-center rounded-full text-muted hover:bg-surface hover:text-ink">
          <Icon name="close" />
        </button>
      )}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-[#0f1022] p-8 text-white md:flex">
        <div>
          <Logo onDark className="h-8" />
          <p className="mt-3 font-serif text-3xl font-bold leading-tight">{t("Votre prochain départ")} <span className="italic text-[#ffc979]">{t("commence ici.")}</span></p>
        </div>
        <StudentsIllustration className="lite-hide mx-auto -mb-8 mt-4 w-full max-w-[340px]" />
        <ul className="relative mt-2 grid grid-cols-3 gap-2 text-center text-[11px] text-white/70">
          {[{ i: "star", t: t("Score par bourse") }, { i: "file", t: t("CV et lettre") }, { i: "people", t: t("Conseiller dédié") }].map((x) => (
            <li key={x.t} className="flex flex-col items-center gap-1.5"><Icon name={x.i} className="h-4 w-4 text-[#3ee0a8]" />{x.t}</li>
          ))}
        </ul>
      </div>
      <div className="relative p-6 sm:p-9">
        <Logo className="mb-6 h-7 md:hidden" />
          <div className="relative grid grid-cols-2 rounded-full border border-line bg-surface p-1 text-sm">
            {(["connexion", "inscription"] as const).map((m) => (
              <button key={m} type="button" onClick={() => { setMode(m); setError(null); }}
                className={`rounded-full py-2 font-semibold transition ${mode === m ? "bg-card text-ink shadow-sm ring-1 ring-line" : "text-muted hover:text-ink"}`}>
                {m === "connexion" ? t("Connexion") : t("Inscription")}
              </button>
            ))}
          </div>
          <h1 className="mt-7 text-[1.65rem] sm:text-3xl leading-tight">{isLogin ? <>{t("Ravis de vous")} <span className="accent">{t("revoir.")}</span></> : <>{t("Votre profil en")} <span className="accent">{t("cinq minutes.")}</span></>}</h1>
          <p className="mt-2 text-sm text-muted">
            {isLogin ? <>{t("Retrouvez vos bourses et votre score.")}{SHOW_DEMO && <> {t("Démo :")} <span className="font-mono text-xs text-brand">{t("demo@example.org")}</span> / <span className="font-mono text-xs text-brand">{t("demo12345")}</span></>}</> : t("Un e-mail et un mot de passe. Ensuite, votre profil sert uniquement à trouver vos bourses.")}
          </p>
          <form onSubmit={submit} className="relative mt-6 space-y-5">
            <div>
              <label className="label" htmlFor="email">{t("E-mail")}</label>
              <input id="email" name="email" type="email" autoComplete={isLogin ? "username" : "email"} inputMode="email" autoCapitalize="none" spellCheck={false} required className="input" placeholder={t("awa@email.com")} value={email} onChange={(e) => { setEmail(e.target.value); setTaken(false); }} onBlur={checkEmail} />
              {taken && !isLogin && (
                <p className="mt-1.5 text-xs text-warm">{t("Un compte existe déjà avec cet e-mail.")} <button type="button" className="font-semibold underline" onClick={() => { setMode("connexion"); setTaken(false); }}>{t("Se connecter")}</button></p>
              )}
            </div>
            <div>
              <label className="label" htmlFor="password">{t("Mot de passe")}</label>
              <div className="relative">
                <input id="password" name="password" type={show ? "text" : "password"} autoComplete={isLogin ? "current-password" : "new-password"} required minLength={isLogin ? 1 : 8} pattern={isLogin ? undefined : "(?=.*[A-Za-z])(?=.*\\d).{8,}"} title={isLogin ? undefined : t("8 caractères minimum, avec au moins une lettre et un chiffre")} className="input pr-10" placeholder={isLogin ? "••••••••" : t("8 caractères, une lettre et un chiffre")} value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink" aria-label={show ? t("Masquer le mot de passe") : t("Afficher le mot de passe")}><Icon name="eye" /></button>
              </div>
              {isLogin && <p className="mt-1.5 text-right text-xs"><Link href="/mot-de-passe-oublie" onClick={() => onClose?.()} className="text-muted hover:text-brand hover:underline">{t("Mot de passe oublié ?")}</Link></p>}
            </div>
            {!isLogin && (
              <div className="-mt-2 space-y-2">
                <div className="flex gap-1">{[0, 1, 2, 3].map((i) => <span key={i} className={`h-1 flex-1 rounded-full ${i < strength(password) ? (strength(password) >= 3 ? "bg-mint" : "bg-gold") : "bg-surface"}`} />)}</div>
                <p className="flex items-center justify-between text-[11px] text-muted">
                  <span>{password ? [t("Trop court"), t("Faible"), t("Correct"), t("Solide"), t("Très solide")][strength(password)] : t("Votre navigateur peut aussi proposer et retenir un mot de passe.")}</span>
                  <button type="button" className="font-semibold text-brand hover:underline" onClick={() => { setPassword(suggestPassword()); setShow(true); }}>{t("Suggérer un mot de passe")}</button>
                </p>
              </div>
            )}
            {!isLogin && (
              <label className="flex items-start gap-2 text-xs text-muted">
                <input type="checkbox" className="mt-0.5 accent-[#3ee0a8]" checked={consent} onChange={(e) => setConsent(e.target.checked)} required />
                <span>{t("J'accepte que mes informations servent au matching et à la préparation de mes candidatures. Elles ne sont jamais vendues et je peux supprimer mon compte à tout moment.")} <Link href="/confidentialite" target="_blank" className="font-semibold text-brand hover:underline">{t("Politique de confidentialité")}</Link></span>
              </label>
            )}
            {error && <p className="text-sm text-danger">{error}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? "…" : isLogin ? t("Se connecter") : t("Créer mon compte")} <Icon name="arrow" /></button>
          </form>
          {!onClose && <p className="mt-6 text-center text-xs text-muted"><Link href="/" className="hover:text-ink">{t("← Retour à l'accueil")}</Link></p>}
      </div>
    </div>
  );
}

