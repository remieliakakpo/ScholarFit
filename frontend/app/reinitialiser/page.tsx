"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import AccountPageCard from "@/components/AccountPageCard";
import Icon from "@/components/Icon";
import { api, setToken } from "@/lib/api";
import { useT } from "@/components/LangProvider";

function ResetForm() {
  const { t } = useT();
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError(t("Les deux mots de passe ne sont pas identiques."));
    setBusy(true);
    setError(null);
    try {
      const { access_token, home } = await api<{ access_token: string; home: string }>("/api/auth/reinitialiser", { method: "POST", body: JSON.stringify({ token, password }) });
      setToken(access_token);
      router.push(home || "/mes-bourses");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!token)
    return (
      <>
        <p className="text-sm text-muted">{t("Ce lien est incomplet. Ouvrez le lien reçu par e-mail tel quel, ou demandez-en un nouveau.")}</p>
        <Link href="/mot-de-passe-oublie" className="btn-primary mt-6 w-full">{t("Demander un nouveau lien")}</Link>
      </>
    );

  return (
    <>
      <p className="mt-2 text-sm text-muted">{t("8 caractères minimum, avec au moins une lettre et un chiffre")}</p>
      <form onSubmit={submit} className="mt-6 space-y-5">
        <div>
          <label className="label" htmlFor="password">{t("Nouveau mot de passe")}</label>
          <div className="relative">
            <input id="password" name="password" type={show ? "text" : "password"} autoComplete="new-password" required minLength={8} pattern="(?=.*[A-Za-z])(?=.*\d).{8,}" title={t("8 caractères minimum, avec au moins une lettre et un chiffre")} className="input pr-10" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink" aria-label={show ? t("Masquer le mot de passe") : t("Afficher le mot de passe")}><Icon name="eye" /></button>
          </div>
        </div>
        <div>
          <label className="label" htmlFor="confirm">{t("Confirmer le mot de passe")}</label>
          <input id="confirm" name="confirm" type={show ? "text" : "password"} autoComplete="new-password" required minLength={8} className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        {error && <p className="text-sm text-danger">{error} {error.includes("lien") || error.includes("link") ? <Link href="/mot-de-passe-oublie" className="font-semibold underline">{t("Demander un nouveau lien")}</Link> : null}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "…" : t("Changer mon mot de passe")} <Icon name="arrow" /></button>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  const { t } = useT();
  return (
    <AccountPageCard>
      <h1 className="text-[1.65rem] leading-tight sm:text-3xl">{t("Nouveau")} <span className="accent">{t("mot de passe")}</span></h1>
      <Suspense><ResetForm /></Suspense>
    </AccountPageCard>
  );
}
