"use client";
import Link from "next/link";
import { Logo } from "./Icon";
import { useT } from "./LangProvider";

const COLS: { t: string; links: [string, string][] }[] = [
  { t: "Explorer", links: [["/bourses", "Bourses d'études"], ["/bourses?kind=stage", "Stages"], ["/bourses?kind=conference", "Conférences"], ["/destinations", "Bourses par pays"], ["/questionnaire", "Mon profil en 5 étapes"]] },
  { t: "Mon espace", links: [["/mes-bourses", "Mes bourses"], ["/suivi", "Suivi des candidatures"], ["/cv", "Mon CV"], ["/profil", "Mon profil"]] },
  { t: "ScholarFit", links: [["/a-propos", "À propos"], ["/#comment", "Comment ça marche"], ["/accompagnement", "Accompagnement"], ["/#offres", "Tarifs"], ["/#questions", "Questions fréquentes"], ["/soutenir", "Soutenir le site"]] },
];

/** Pied de page commun au site public et à l'espace connecté. */
export default function Footer({ loggedIn }: { loggedIn: boolean }) {
  const { t } = useT();
  return (
    <footer className="border-t border-line bg-card/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 grid-cols-2 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="col-span-2 md:col-span-1">
          <Link href="/" aria-label={t("Accueil ScholarFit")}><Logo /></Link>
          <p className="mt-4 max-w-xs text-sm text-muted">{t("Les bourses d'études, stages et conférences du monde entier, classés selon votre profil, avec un accompagnement par des experts.")}</p>
          {!loggedIn && <Link href="/connexion?mode=inscription" className="btn-primary mt-5">{t("Créer mon compte")}</Link>}
        </div>
        {COLS.map((c) => (
          <nav key={c.t} aria-label={t(c.t)}>
            <p className="text-sm font-semibold text-ink">{t(c.t)}</p>
            <ul className="mt-3 space-y-2 text-sm">
              {c.links.map(([href, label]) => <li key={href}><Link href={href} className="text-muted transition hover:text-brand">{t(label)}</Link></li>)}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-5 text-xs text-muted sm:px-6">
          <span>© {new Date().getFullYear()} ScholarFit. {t("Tous droits réservés.")}</span>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-1" aria-label={t("Informations légales")}>
            <Link href="/conditions" className="hover:text-brand">{t("Conditions d'utilisation")}</Link>
            <Link href="/confidentialite" className="hover:text-brand">{t("Confidentialité")}</Link>
            <span>{t("Offres mises à jour automatiquement chaque semaine.")}</span>
          </nav>
        </div>
      </div>
    </footer>
  );
}
