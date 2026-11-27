"use client";
import { useEffect, useState } from "react";
import Icon from "./Icon";
import { api } from "@/lib/api";
import { Me, refreshAuth, useAuth } from "@/lib/useAuth";
import { useT } from "./LangProvider";

/** Carte « Mon compte » du profil : nom affiché dans « Salut, … » et état de l'adresse e-mail. */
export default function AccountCard() {
  const { t } = useT();
  const { me } = useAuth();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (me) setName(me.name || me.display_name); }, [me]);
  if (!me) return null;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setMsg(null); setError(null);
    try {
      await api<Me>("/api/auth/me", { method: "PATCH", body: JSON.stringify({ name }) });
      refreshAuth();
      setMsg(t("Nom enregistré."));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="card p-5">
      <p className="flex items-center gap-2 text-sm font-semibold"><Icon name="user" className="h-4 w-4 text-brand" />{t("Mon compte")}</p>
      <label className="label mt-3" htmlFor="account-name">{t("Prénom ou nom d'utilisateur")}</label>
      <div className="flex gap-2">
        <input id="account-name" className="input" required minLength={2} maxLength={80} autoComplete="given-name" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn-ghost shrink-0 px-4" disabled={busy || name.trim() === (me.name || me.display_name)}>{busy ? "…" : t("Enregistrer")}</button>
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted" title={me.email}>
        <Icon name="mail" className="h-3.5 w-3.5 shrink-0" /><span className="min-w-0 truncate">{me.email}</span>
        <span className={`ml-auto shrink-0 ${me.email_verified ? "text-ok" : "text-warm"}`}>{me.email_verified ? t("✓ confirmé") : t("à confirmer")}</span>
      </p>
      {msg && <p className="mt-2 text-xs text-ok">{msg}</p>}
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </form>
  );
}
