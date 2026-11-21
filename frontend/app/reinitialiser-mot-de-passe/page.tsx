"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, setSignedIn } from "@/lib/api";
import { useT } from "@/components/LangProvider";

/** Lien reçu par e-mail : choix d'un nouveau mot de passe (valable 1 heure, une seule fois). */
function Page() {
  const { t } = useT();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError(t("Les deux mots de passe ne sont pas identiques."));
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/reinitialiser-mot-de-passe", { method: "POST", body: JSON.stringify({ token, password }) });
      setSignedIn(false); // toutes les sessions ont été fermées
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md py-10">
      <div className="card p-8">
        <h1 className="text-2xl">{t("Nouveau mot de passe")}</h1>
        {done ? (
          <>
            <p className="mt-3 text-sm text-ok">{t("Mot de passe changé. Par sécurité, vous avez été déconnecté de tous vos appareils.")}</p>
            <Link href="/connexion" className="btn-primary mt-6 w-full">{t("Se connecter")}</Link>
          </>
        ) : !token ? (
          <p className="mt-3 text-sm text-danger">{t("Lien incomplet : ouvrez le lien reçu par e-mail en entier.")}</p>
        ) : (
          <form onSubmit={submit} className="mt-5 space-y-4">
            <div>
              <label className="label" htmlFor="password">{t("Nouveau mot de passe")}</label>
              <input id="password" type="password" autoComplete="new-password" required minLength={8} pattern={"(?=.*[A-Za-z])(?=.*\\d).{8,}"} title={t("8 caractères minimum, avec au moins une lettre et un chiffre")} className="input" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="confirm">{t("Confirmer le mot de passe")}</label>
              <input id="confirm" type="password" autoComplete="new-password" required className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? "…" : t("Enregistrer le mot de passe")}</button>
          </form>
        )}
        {!done && <p className="mt-6 text-center text-xs text-muted"><Link href="/mot-de-passe-oublie" className="hover:text-ink">{t("Demander un nouveau lien")}</Link></p>}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return <Suspense><Page /></Suspense>;
}
