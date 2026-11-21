"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/LangProvider";

/** Demande d'un lien de réinitialisation. La réponse est la même que l'adresse ait un compte ou non. */
export default function ForgotPasswordPage() {
  const { t } = useT();
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ message: string }>("/api/auth/mot-de-passe-oublie", { method: "POST", body: JSON.stringify({ email }) });
      setDone(r.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md py-10">
      <div className="card p-8">
        <h1 className="text-2xl">{t("Mot de passe oublié")}</h1>
        {done ? (
          <>
            <p className="mt-3 text-sm text-ok">{done}</p>
            <p className="mt-2 text-sm text-muted">{t("Pensez à regarder dans les courriers indésirables.")}</p>
          </>
        ) : (
          <form onSubmit={submit} className="mt-5 space-y-4">
            <p className="text-sm text-muted">{t("Indiquez l'adresse de votre compte : nous vous envoyons un lien pour choisir un nouveau mot de passe.")}</p>
            <div>
              <label className="label" htmlFor="email">{t("E-mail")}</label>
              <input id="email" type="email" autoComplete="email" inputMode="email" autoCapitalize="none" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? "…" : t("Recevoir le lien")}</button>
          </form>
        )}
        <p className="mt-6 text-center text-xs text-muted"><Link href="/connexion" className="hover:text-ink">{t("← Retour à la connexion")}</Link></p>
      </div>
    </div>
  );
}
