"use client";
import { useState } from "react";
import Icon from "./Icon";
import { api } from "@/lib/api";
import { useT } from "./LangProvider";

/** Bandeau tant que l'adresse e-mail n'est pas confirmée, avec renvoi du lien. */
export default function VerifyEmailBanner({ email }: { email: string }) {
  const { t } = useT();
  const [state, setState] = useState<"idle" | "busy" | "sent" | "error">("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;

  async function resend() {
    setState("busy");
    try {
      await api("/api/auth/verification/envoyer", { method: "POST" });
      setState("sent");
    } catch (e) {
      setMsg((e as Error).message);
      setState("error");
    }
  }

  return (
    <div className="border-b border-line bg-gold/10 px-4 py-2.5 sm:px-8">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <Icon name="mail" className="h-4 w-4 shrink-0 text-gold" />
        <p className="min-w-0 flex-1 text-ink">
          {state === "sent"
            ? t("Nouveau lien envoyé à {email}. Pensez à regarder dans les courriers indésirables.", { email })
            : state === "error" ? msg
            : t("Confirmez votre adresse e-mail : nous avons envoyé un lien à {email}.", { email })}
        </p>
        {state !== "sent" && (
          <button type="button" onClick={resend} disabled={state === "busy"} className="text-sm font-semibold text-brand hover:underline disabled:opacity-50">
            {state === "busy" ? "…" : t("Renvoyer le lien")}
          </button>
        )}
        <button type="button" onClick={() => setHidden(true)} aria-label={t("Fermer")} className="grid h-7 w-7 place-items-center rounded-full text-muted hover:bg-surface hover:text-ink">
          <Icon name="close" className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
