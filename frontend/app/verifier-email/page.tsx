"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AccountPageCard from "@/components/AccountPageCard";
import Icon from "@/components/Icon";
import { api, getToken } from "@/lib/api";
import { homeFor, refreshAuth, useAuth } from "@/lib/useAuth";
import { useT } from "@/components/LangProvider";

function Verify() {
  const { t } = useT();
  const { me } = useAuth();
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"busy" | "ok" | "error">(token ? "busy" : "error");
  const [msg, setMsg] = useState<string | null>(token ? null : t("Ce lien est incomplet. Ouvrez le lien reçu par e-mail tel quel."));
  const done = useRef(false);

  useEffect(() => {
    if (!token || done.current) return;
    done.current = true;
    api("/api/auth/verification", { method: "POST", body: JSON.stringify({ token }) })
      .then(() => { setState("ok"); if (getToken()) refreshAuth(); })
      .catch((e) => { setMsg((e as Error).message); setState("error"); });
  }, [token]);

  if (state === "busy") return <p className="mt-3 text-sm text-muted">{t("Vérification du lien…")}</p>;
  if (state === "ok")
    return (
      <>
        <p className="mt-3 flex items-center gap-2 text-sm text-ok"><Icon name="check" className="h-4 w-4" />{t("Votre adresse e-mail est confirmée. Merci !")}</p>
        <Link href={me ? homeFor(me) : "/connexion"} className="btn-primary mt-6 w-full">{me ? t("Aller à mon espace") : t("Se connecter")} <Icon name="arrow" /></Link>
      </>
    );
  return (
    <>
      <p className="mt-3 text-sm text-danger">{msg}</p>
      <Link href={me ? homeFor(me) : "/connexion"} className="btn-ghost mt-6 w-full">{me ? t("Aller à mon espace") : t("Se connecter")}</Link>
    </>
  );
}

export default function VerifyEmailPage() {
  const { t } = useT();
  return (
    <AccountPageCard>
      <h1 className="text-[1.65rem] leading-tight sm:text-3xl">{t("Confirmation de")} <span className="accent">{t("votre e-mail")}</span></h1>
      <Suspense><Verify /></Suspense>
    </AccountPageCard>
  );
}
