import type { Metadata } from "next";
import Support from "@/components/Support";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getT();
  return { title: t("Soutenir ScholarFit"), description: t("Faire un don pour soutenir le travail de l'équipe ScholarFit.") };
}

const USES = [
  { t: "Rechercher et vérifier les offres", d: "Chaque bourse, stage et conférence est relu, avec ses dates et ses liens officiels." },
  { t: "Accompagner les étudiants", d: "Des experts aident les candidats qui en ont le plus besoin à monter un dossier solide." },
  { t: "Faire vivre la plateforme", d: "Hébergement, nouvelles sources en Afrique et dans le monde, alertes de dates limites." },
];

export default async function Page() {
  const { t } = await getT();
  return (
    <div className="mx-auto max-w-6xl space-y-12 py-6">
      <Support asPage />
      <section>
        <p className="eyebrow">{t("À quoi servent les dons")}</p>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {USES.map((u, i) => (
            <div key={u.t} className="card p-5">
              <span className="text-xs font-semibold text-brand">0{i + 1}</span>
              <p className="mt-2 font-semibold">{t(u.t)}</p>
              <p className="mt-1 text-sm text-muted">{t(u.d)}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
