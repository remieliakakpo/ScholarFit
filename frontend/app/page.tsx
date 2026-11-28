import Link from "next/link";
import Chat from "@/components/Chat";
import { CountryCarousel, FlagMarquee, HeroGlobe, LiveStats } from "@/components/HomeLive";
import Icon from "@/components/Icon";
import AdvisorBanner from "@/components/AdvisorBanner";
import Reveal from "@/components/Reveal";
import Support from "@/components/Support";
import KindsShowcase from "@/components/KindsShowcase";
import { ChecklistArt } from "@/components/Illustrations";
import { getT } from "@/lib/i18n-server";

const STEPS = [
  { n: "01", icon: "user", t: "Répondez à 5 questions", d: "Niveau, nationalité, domaine, pays visés, langues. Deux minutes, sans compte." },
  { n: "02", icon: "star", t: "Découvrez votre score", d: "Chaque bourse reçoit un score selon votre profil, avec vos points forts et ce qui manque." },
  { n: "03", icon: "file", t: "Préparez votre dossier", d: "Conditions, documents à fournir, lien officiel, CV et lettre adaptés à la bourse." },
  { n: "04", icon: "people", t: "Postulez, seul ou accompagné", d: "Vous envoyez vous-même, ou un expert prépare et dépose votre candidature." },
];

const FAQ = [
  { q: "La recherche est-elle gratuite ?", a: "Oui. Le questionnaire, le score, les conditions, la liste des documents et le suivi sont gratuits. Votre premier dossier CV et lettre adaptés à une bourse est offert, ensuite l'abonnement est à 2 500 F CFA par mois. Si vous préférez qu'un expert dépose votre candidature : Standard 15 000 F CFA pour 1 bourse, Premium 35 000 F CFA pour 3 bourses." },
  { q: "D'où viennent les bourses ?", a: "Elles sont collectées dans le monde entier sur les sites officiels (ministères, universités, fondations), puis vérifiées. Chaque fiche donne le lien officiel de candidature." },
  { q: "Que se passe-t-il quand une date limite est passée ?", a: "La bourse est signalée comme clôturée et, quand c'est possible, on indique la date attendue de la prochaine session. Les bourses qui ferment bientôt passent en tête." },
  { q: "Pourquoi créer un compte ?", a: "Pour voir votre score sur chaque bourse, enregistrer vos candidatures, recevoir les rappels de dates limites et demander un accompagnement." },
  { q: "Que devient mon profil ?", a: "Il sert uniquement au matching et à la préparation de vos documents. Il n'est jamais vendu, et vous pouvez supprimer votre compte à tout moment." },
];

export default async function Home() {
  const { t } = await getT();
  return (
    <div className="overflow-x-hidden">
      {/* Héros : globe du monde entier */}
      <section className="relative">
        <div className="bg-grid pointer-events-none absolute inset-0" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-6 px-4 pb-10 pt-10 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:pt-14">
          <div className="lg:py-16">
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1 text-xs text-muted">
                {t("Bourses, stages et conférences du monde entier")}
              </span>
            </Reveal>
            <Reveal delay={80}>
              <h1 className="mt-6 text-[2.1rem] leading-[1.1] sm:text-[2.8rem] lg:text-[3.5rem]">
                {t("La bourse qui vous correspond,")} <span className="accent">{t("où qu'elle soit.")}</span>
              </h1>
            </Reveal>
            <Reveal delay={160}>
              <p className="mt-6 max-w-lg text-base text-muted sm:text-lg">
                {t("Répondez à cinq questions. ScholarFit compare votre profil aux bourses ouvertes dans tous les pays, vous donne un score pour chacune et la liste exacte de ce qu'il faut fournir.")}
              </p>
            </Reveal>
            <Reveal delay={240}>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link href="/questionnaire" className="btn-primary">{t("Trouver mes bourses")} <Icon name="arrow" /></Link>
                <Link href="/bourses" className="btn-ghost">{t("Voir toutes les bourses")}</Link>
              </div>
              <p className="mt-4 text-xs text-muted">{t("Gratuit, sans compte pour commencer.")}</p>
            </Reveal>
          </div>
          <Reveal delay={120} className="relative">
            <HeroGlobe />
          </Reveal>
        </div>
        <div className="relative mx-auto max-w-6xl px-4 pb-14 sm:px-6">
          <Reveal><LiveStats /></Reveal>
          <Reveal delay={120} className="mt-10"><FlagMarquee /></Reveal>
        </div>
      </section>

      {/* Pays */}
      <section className="border-y border-line bg-surface py-10">
        <div className="mx-auto mb-5 flex max-w-6xl flex-wrap items-end justify-between gap-3 px-4 sm:px-6">
          <div>
            <p className="eyebrow">{t("Par pays d'études")}</p>
            <h2 className="mt-2 text-2xl sm:text-3xl">{t("Où partir, et combien de bourses vous attendent.")}</h2>
          </div>
          <Link href="/bourses" className="text-sm font-semibold text-brand hover:underline">{t("Tous les pays")} →</Link>
        </div>
        <div className="mx-auto max-w-6xl px-2.5 sm:px-4.5"><CountryCarousel /></div>
      </section>

      {/* Stages et conférences */}
      <section id="stages" className="kinds-section mx-auto max-w-6xl scroll-mt-20 px-4 pt-20 sm:px-6 sm:pt-24">
        <Reveal>
          <p className="eyebrow">{t("Au-delà des bourses")}</p>
          <h2 className="mt-3 max-w-2xl text-[1.9rem] leading-tight sm:text-5xl">{t("Stages et conférences,")} <span className="accent">{t("partout dans le monde.")}</span></h2>
          <p className="mt-4 max-w-xl text-muted">{t("Les mêmes filtres, le même score et les mêmes rappels de dates limites s'appliquent aux stages et aux conférences.")}</p>
        </Reveal>
        <Reveal delay={120} className="mt-10"><KindsShowcase /></Reveal>
      </section>

      {/* Parcours */}
      <section id="comment" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:py-24 sm:px-6">
        <Reveal>
          <p className="eyebrow">{t("Comment ça marche")}</p>
          <h2 className="mt-3 max-w-2xl text-[1.9rem] leading-tight sm:text-4xl lg:text-5xl">{t("De votre profil à votre dossier,")} <span className="accent">{t("pas à pas.")}</span></h2>
        </Reveal>
        <ol className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} as="li" delay={i * 90} className="card group relative overflow-hidden p-6 transition hover:-translate-y-1 hover:border-brand/40">
              <span className="font-mono text-xs text-brand">{s.n}</span>
              <span className="mt-6 grid h-11 w-11 place-items-center rounded-2xl bg-brand-soft text-brand transition group-hover:scale-110"><Icon name={s.icon} className="h-5 w-5" /></span>
              <p className="mt-5 font-serif text-xl font-semibold">{t(s.t)}</p>
              <p className="mt-2 text-sm text-muted">{t(s.d)}</p>
            </Reveal>
          ))}
        </ol>
        <Reveal delay={200} className="mt-10">
          <div className="flex flex-col items-start justify-between gap-5 rounded-3xl border border-line bg-[linear-gradient(120deg,color-mix(in_srgb,var(--color-mint)_14%,var(--color-card)),var(--color-card)_55%,color-mix(in_srgb,var(--color-gold)_12%,var(--color-card)))] p-6 sm:flex-row sm:items-center sm:p-8">
            <div>
              <p className="font-serif text-2xl font-semibold">{t("Prêt ? Le questionnaire prend deux minutes.")}</p>
              <p className="mt-1 text-sm text-muted">{t("Vous voyez vos premières bourses tout de suite. Votre score complet s'affiche avec un compte gratuit.")}</p>
            </div>
            <Link href="/questionnaire" className="btn-primary shrink-0">{t("Commencer le questionnaire")} <Icon name="arrow" /></Link>
          </div>
        </Reveal>
      </section>

      {/* Fiche bourse */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:py-24 sm:px-6 lg:grid-cols-2">
          <Reveal>
            <p className="eyebrow">{t("Chaque bourse, en clair")}</p>
            <h2 className="mt-3 text-[1.9rem] leading-tight sm:text-4xl lg:text-5xl">{t("Les conditions, les pièces,")} <span className="accent">{t("le bon lien.")}</span></h2>
            <p className="mt-4 max-w-lg text-muted">{t("Pour chaque bourse : qui peut postuler, ce qu'elle finance, les documents à préparer, les étapes pour candidater et le lien officiel vérifié. Les dates limites proches sont signalées en priorité.")}</p>
            <Link href="/bourses" className="btn-ghost mt-8">{t("Parcourir les bourses")} <Icon name="arrow" /></Link>
          </Reveal>
          <Reveal delay={120}>
            <div className="card overflow-hidden shadow-[0_40px_80px_-40px_rgba(0,0,0,0.5)]">
              <div className="flex items-center justify-between border-b border-line px-5 py-4">
                <span className="text-sm font-semibold">{t("Bourse d'excellence d'un gouvernement")}</span>
                <span className="rounded-full bg-warm-soft px-2.5 py-0.5 text-[11px] font-semibold text-warm">{t("J-12 · urgent")}</span>
              </div>
              <div className="grid gap-px bg-line sm:grid-cols-2">
                <div className="bg-card p-5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted">{t("Conditions")}</p>
                  <ul className="mt-3 space-y-2 text-sm">
                    {["Moins de 30 ans", "Licence obtenue", "Nationalité hors UE"].map((x) => <li key={x} className="flex gap-2"><Icon name="check" className="mt-0.5 h-4 w-4 text-brand" />{t(x)}</li>)}
                  </ul>
                </div>
                <div className="bg-card p-5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted">{t("Documents")}</p>
                  <ul className="mt-3 space-y-2 text-sm">
                    {["CV", "Lettre de motivation", "Relevés de notes"].map((x) => <li key={x} className="flex gap-2"><Icon name="file" className="mt-0.5 h-4 w-4 text-gold" />{t(x)}</li>)}
                  </ul>
                </div>
              </div>
              <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-4">
                <span className="flex items-center gap-2 text-xs text-muted"><span className="h-2 w-2 rounded-full bg-ok" />{t("Lien officiel vérifié")}</span>
                <span className="text-xs text-muted">{t("Exemple")}</span>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Offres */}
      <section id="offres" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-12 sm:py-16 sm:px-6">
        <Reveal><AdvisorBanner /></Reveal>
      </section>

      {/* Assistant */}
      <section id="assistant" className="scroll-mt-20 border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:py-24 sm:px-6">
          <Reveal>
            <p className="eyebrow">{t("Une question précise ?")}</p>
            <h2 className="mt-3 max-w-2xl text-[1.9rem] leading-tight sm:text-4xl lg:text-5xl">{t("Demandez à l'assistant,")} <span className="accent">{t("avec vos mots.")}</span></h2>
            <p className="mt-4 max-w-xl text-muted">{t("Décrivez votre profil en une phrase et recevez les bourses qui vous correspondent, avec le lien officiel.")}</p>
          </Reveal>
          <Reveal delay={120} className="mt-10"><Chat /></Reveal>
        </div>
      </section>

      {/* Questions */}
      <section id="questions" className="mx-auto grid max-w-6xl scroll-mt-20 gap-10 px-4 py-16 sm:py-24 sm:px-6 lg:grid-cols-[1fr_1.5fr]">
        <Reveal>
          <p className="eyebrow">{t("Questions fréquentes")}</p>
          <h2 className="mt-3 text-3xl sm:text-4xl">{t("Avant de vous lancer.")}</h2>
          <ChecklistArt className="lite-hide mt-8 hidden w-56 lg:block" />
        </Reveal>
        <div className="space-y-3">
          {FAQ.map((f, i) => (
            <Reveal key={f.q} delay={i * 60}>
              <details className="card group p-5 open:border-brand/40">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold">
                  {t(f.q)}
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-line text-muted transition group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted">{t(f.a)}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Appel final */}
      <section id="soutenir" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-16 sm:px-6">
        <Reveal><Support compact /></Reveal>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        <Reveal>
          <div className="relative overflow-hidden rounded-[2rem] border border-line bg-card px-6 py-16 text-center sm:px-14">
            <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-mint/20 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-24 -left-10 h-60 w-60 rounded-full bg-gold/20 blur-3xl" />
            <h2 className="relative mx-auto max-w-2xl text-[1.9rem] leading-tight sm:text-4xl lg:text-5xl">{t("Votre prochaine rentrée se prépare")} <span className="accent">{t("maintenant.")}</span></h2>
            <p className="relative mx-auto mt-4 max-w-md text-muted">{t("Cinq questions, et vous savez où postuler, avant quelle date et avec quels documents.")}</p>
            <div className="relative mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/questionnaire" className="btn-primary">{t("Trouver mes bourses")} <Icon name="arrow" /></Link>
              <Link href="/connexion?mode=inscription" className="btn-ghost">{t("Créer un compte")}</Link>
            </div>
          </div>
        </Reveal>
      </section>
    </div>
  );
}
