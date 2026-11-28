"use client";
import Link from "next/link";
import { useState } from "react";
import AccountPageCard from "@/components/AccountPageCard";
import Icon from "@/components/Icon";
import { api } from "@/lib/api";
import { useT } from "@/components/LangProvider";

export default function ForgotPasswordPage() {
  const { t } = useT();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/mot-de-passe-oublie", { method: "POST", body: JSON.stringify({ email }) });
      setSent(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AccountPageCard>
      <h1 className="text-[1.65rem] leading-tight sm:text-3xl">{t("Mot de passe")} <span className="accent">{t("oublié ?")}</span></h1>
      {sent ? (
        <>
          <p className="mt-3 text-sm text-muted">{t("Si un compte existe pour {email}, un lien pour choisir un nouveau mot de passe vient d'y être envoyé. Il est valable une heure. Pensez à regarder dans les courriers indésirables.", { email })}</p>
          <Link href="/connexion" className="btn-primary mt-6 w-full">{t("Retour à la connexion")} <Icon name="arrow" /></Link>
          <button type="button" onClick={() => setSent(false)} className="mt-3 w-full text-center text-xs text-muted hover:text-ink">{t("Utiliser une autre adresse")}</button>
        </>
      ) : (
        <>
          <p className="mt-2 text-sm text-muted">{t("Indiquez l'adresse e-mail de votre compte : nous vous envoyons un lien pour choisir un nouveau mot de passe.")}</p>
          <form onSubmit={submit} className="mt-6 space-y-5">
            <div>
              <label className="label" htmlFor="email">{t("E-mail")}</label>
              <input id="email" name="email" type="email" autoComplete="email" inputMode="email" autoCapitalize="none" spellCheck={false} required className="input" placeholder={t("awa@email.com")} value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? "…" : t("Recevoir le lien")} <Icon name="arrow" /></button>
          </form>
          <p className="mt-6 text-center text-xs text-muted"><Link href="/connexion" className="hover:text-ink">{t("← Retour à la connexion")}</Link></p>
        </>
      )}
    </AccountPageCard>
  );
}
