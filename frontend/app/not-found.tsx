import Link from "next/link";
import { getT } from "@/lib/i18n-server";
export default async function NotFound() {
  const { t } = await getT();
  return (
    <div className="card mx-auto mt-10 max-w-md p-8 text-center">
      <h1 className="text-2xl">{t("Page introuvable")}</h1>
      <p className="mt-2 text-sm text-muted">{t("Le lien est peut-être ancien ou la bourse a été retirée.")}</p>
      <Link href="/bourses" className="btn-primary mt-4">{t("Voir les bourses")}</Link>
    </div>
  );
}
