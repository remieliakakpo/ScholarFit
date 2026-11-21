"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/LangProvider";

/** Lien en bas des e-mails d'alerte. Un clic de confirmation (et pas une simple ouverture du lien),
 *  pour qu'un logiciel qui analyse les e-mails ne désabonne pas la personne à sa place. */
function Page() {
  const { t } = useT();
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");

  async function confirm() {
    setState("busy");
    try {
      const r = await api<{ message: string }>("/api/alertes/desabonner", { method: "POST", body: JSON.stringify({ token }) });
      setMsg(r.message);
      setState("done");
    } catch (e) {
      setMsg((e as Error).message);
      setState("error");
    }
  }

  return (
    <div className="mx-auto max-w-md py-10">
      <div className="card p-8 text-center">
        <h1 className="text-2xl">{t("E-mails d'alerte")}</h1>
        {state === "done" ? (
          <p className="mt-3 text-sm text-ok">{msg}</p>
        ) : state === "error" ? (
          <p className="mt-3 text-sm text-danger">{msg}</p>
        ) : !token ? (
          <p className="mt-3 text-sm text-danger">{t("Lien incomplet : ouvrez le lien reçu par e-mail en entier.")}</p>
        ) : (
          <>
            <p className="mt-3 text-sm text-muted">{t("Vous ne recevrez plus les e-mails de nouvelles bourses et de rappels de dates limites. Les alertes restent visibles dans votre espace.")}</p>
            <button type="button" onClick={confirm} disabled={state === "busy"} className="btn-primary mt-6 w-full">{state === "busy" ? "…" : t("Ne plus recevoir ces e-mails")}</button>
          </>
        )}
        <p className="mt-6 text-xs text-muted"><Link href="/profil" className="hover:text-ink">{t("Régler mes alertes dans mon profil")}</Link></p>
      </div>
    </div>
  );
}

export default function UnsubscribePage() {
  return <Suspense><Page /></Suspense>;
}
