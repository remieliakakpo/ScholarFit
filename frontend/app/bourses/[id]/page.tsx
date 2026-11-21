// Page rendue côté serveur : elle peut être indexée par les moteurs de recherche.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DeadlineBadge } from "@/components/ScholarshipCard";
import Flag from "@/components/Flag";
import Icon from "@/components/Icon";
import AdvisorBanner from "@/components/AdvisorBanner";
import DetailActions from "@/components/DetailActions";
import ScholarshipTools from "@/components/ScholarshipTools";
import { Meta, Scholarship, applyUrl, deadlineInfo, formatAmount, formatDate } from "@/lib/api";
import { getT } from "@/lib/i18n-server";
import { Lang, countryName } from "@/lib/i18n";

const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";

async function load(id: string, lang: Lang = "fr"): Promise<{ s: Scholarship; meta: Meta } | null> {
  try {
    const [r, m] = await Promise.all([
      fetch(`${API}/api/scholarships/${encodeURIComponent(id)}${lang !== "fr" ? `?lang=${lang}` : ""}`, { cache: "no-store" }),
      fetch(`${API}/api/meta${lang !== "fr" ? `?lang=${lang}` : ""}`, { next: { revalidate: 3600 } }),
    ]);
    if (!r.ok) return null;
    return { s: await r.json(), meta: await m.json() };
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { t, lang } = await getT();
  const data = await load((await params).id, lang);
  if (!data) return { title: t("Bourse introuvable") };
  const { s } = data;
  const description = [s.organization, s.deadline ? `${t("Date limite")} : ${s.deadline}` : null, s.summary].filter(Boolean).join(" · ").slice(0, 300);
  // Aperçu du lien (WhatsApp, Facebook, LinkedIn…) : titre, résumé et image générée (opengraph-image.tsx)
  return {
    title: s.title,
    description,
    alternates: { canonical: `/bourses/${s.id}` },
    openGraph: { title: s.title, description, type: "article", url: `/bourses/${s.id}`, siteName: "ScholarFit", locale: lang === "en" ? "en_US" : "fr_FR" },
    twitter: { card: "summary_large_image", title: s.title, description },
  };
}

const COVERAGE: Record<string, string> = { frais: "Frais de scolarité", logement: "Logement", voyage: "Billet d'avion", allocation: "Allocation mensuelle", assurance: "Assurance santé" };
const GROUPS: Record<string, string> = { AFRICA: "un pays africain", EU: "un pays de l'Union européenne", FRANCOPHONIE: "un pays de la Francophonie", DEVELOPING: "un pays en développement" };
const TARGETS: Record<string, string> = { refugie: "aux personnes réfugiées", handicap: "aux personnes en situation de handicap", revenus_modestes: "aux étudiants de familles à revenus modestes", femmes: "aux femmes", premiere_generation: "aux étudiants de première génération" };

/** Ce que chaque pièce demande concrètement (utilisé quand la fiche ne le précise pas). */
const DOC_DETAIL: Record<string, string> = {
  cv: "Une à deux pages, à jour, centrées sur votre parcours scolaire, vos expériences et vos engagements.",
  lettre: "Une page qui explique votre projet d'études, pourquoi ce programme et ce que vous ferez ensuite.",
  recommandation: "En général deux lettres d'enseignants ou d'encadrants qui vous connaissent bien. Demandez-les au moins trois semaines avant.",
  releves: "Les relevés des dernières années d'études, souvent traduits en anglais ou en français et certifiés conformes.",
  test_langue: "Un résultat officiel récent (moins de deux ans en général) au niveau demandé.",
  projet_recherche: "Deux à cinq pages : sujet, question de recherche, méthode, calendrier et directeur pressenti si possible.",
  passeport: "Valide au moins six mois après la date prévue d'arrivée. Lancez la demande tôt si vous n'en avez pas.",
  certificat_medical: "Certificat récent signé par un médecin agréé, parfois sur un formulaire fourni par le programme.",
  lettre_admission: "Lettre d'admission ou de pré-admission de l'université d'accueil, si le programme la demande au dépôt.",
  photo: "Photo d'identité récente sur fond clair, au format demandé.",
  portfolio: "Sélection de vos travaux (arts, design, architecture), en PDF ou en lien en ligne.",
  justificatif_revenus: "Attestation de revenus ou de non-imposition des parents, pour les bourses sur critères sociaux.",
  diplome: "Copie du dernier diplôme obtenu, ou une attestation de réussite s'il n'est pas encore délivré.",
};

const DEFAULT_STEPS = [
  "Vérifiez que vous remplissez toutes les conditions ci-dessus, en particulier la nationalité, le niveau et l'âge.",
  "Rassemblez les documents demandés. Les traductions, certifications et lettres de recommandation prennent souvent plusieurs semaines.",
  "Rédigez votre lettre de motivation et adaptez votre CV à cette bourse. Vous pouvez les préparer depuis votre espace ScholarFit.",
  "Créez votre compte sur le site officiel et remplissez le formulaire de candidature en ligne.",
  "Envoyez votre candidature avant la date limite, gardez l'accusé de réception et notez la date des résultats.",
];

type T = (fr: string, vars?: Record<string, string | number | null | undefined>) => string;
const LANG_NAMES: Record<string, string> = { fr: "français", en: "anglais", de: "allemand", es: "espagnol", ar: "arabe", pt: "portugais", it: "italien" };

function conditions(s: Scholarship, meta: Meta, t: T, lang: Lang): string[] {
  if (s.eligibility_notes?.length) return s.eligibility_notes;
  const c = (x: string) => countryName(x, lang, meta.countries[x]);
  const or = ` ${t("ou")} `;
  const out: string[] = [];
  if (s.eligible_nationalities.includes("ALL") || !s.eligible_nationalities.length) out.push(t("Ouverte à toutes les nationalités."));
  else out.push(t("Être ressortissant de {list}.", { list: s.eligible_nationalities.map((n) => (GROUPS[n] ? t(GROUPS[n]) : c(n))).join(", ") }));
  if (s.excluded_nationalities.length) out.push(t("Les ressortissants de {list} ne peuvent pas postuler.", { list: s.excluded_nationalities.map(c).join(", ") }));
  if (s.levels.length) out.push(t("Postuler pour un diplôme de niveau {list}.", { list: s.levels.map((l) => t(meta.levels[l] ?? l).split(" : ").pop()).join(`,${or}`) }));
  if (s.domains.length && !s.domains.includes("tous")) out.push(t("Étudier dans l'un de ces domaines : {list}.", { list: s.domains.map((d) => t(meta.domains[d] ?? d)).join(", ") }));
  if (s.max_age) out.push(t("Avoir {n} ans au plus à la date limite de candidature.", { n: s.max_age }));
  if (s.min_grade) out.push(t("Avoir une moyenne d'au moins {n}/20.", { n: s.min_grade }));
  const tests = Object.entries(s.language_tests);
  if (tests.length) out.push(t("Justifier d'un niveau de langue : {list}.", { list: tests.map(([k, v]) => `${k} ${v}`).join(or) }));
  else if (s.languages.length) out.push(t("Pouvoir étudier en {list}.", { list: s.languages.map((l) => (LANG_NAMES[l] ? t(LANG_NAMES[l]) : l)).join(or) }));
  if (s.target_groups.length) out.push(t("Bourse réservée {list}.", { list: s.target_groups.map((g) => (TARGETS[g] ? t(TARGETS[g]) : g)).join(or) }));
  return out;
}

function documents(s: Scholarship, meta: Meta, t: T): { label: string; detail?: string }[] {
  const det = (code: string) => (DOC_DETAIL[code] ? t(DOC_DETAIL[code]) : undefined);
  if (s.documents?.length) return s.documents.map((d) => ({ label: t(d.label), detail: d.detail ? t(d.detail) : det(d.code) }));
  return s.requirements.map((r) => ({ label: t(meta.requirements[r] ?? r), detail: det(r) }));
}

const LINK: Record<string, { t: string; cls: string }> = {
  ok: { t: "Lien officiel vérifié", cls: "text-ok" },
  redirige: { t: "Le site officiel a changé d'adresse, le lien suit la nouvelle", cls: "text-gold-dark" },
  casse: { t: "Le site officiel ne répond pas en ce moment, réessayez plus tard ou recherchez le programme par son nom", cls: "text-warm" },
};

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { t, lang } = await getT();
  const data = await load((await params).id, lang);
  if (!data) notFound();
  const { s, meta } = data;
  const dl = deadlineInfo(s, lang);
  const conds = conditions(s, meta, t, lang);
  const docs = documents(s, meta, t);
  const steps = s.application_steps?.length ? s.application_steps : DEFAULT_STEPS.map((x) => t(x));
  const url = applyUrl(s);
  const link = s.link_status ? LINK[s.link_status] : undefined;
  const fd = (d: string | null) => formatDate(d, lang);
  const facts: [string, string, string][] = [
    ["medal", t("Financement"), formatAmount(s, lang)],
    ["calendar", t("Date limite"), s.deadline ? fd(s.deadline) : t("Variable selon le programme")],
    ["cap", t("Niveaux"), s.levels.map((l) => t(meta.levels[l] ?? l).split(" : ").pop()).join(" · ") || t("Non précisé")],
    ["globe", t("Pays d'études"), s.study_countries.map((c) => countryName(c, lang, meta.countries[c])).join(", ") || t("Plusieurs pays")],
  ];
  if (s.event_start) facts.splice(1, 0, ["calendar", t("Dates"), s.event_end && s.event_end !== s.event_start ? t("Du {a} au {b}", { a: fd(s.event_start), b: fd(s.event_end) }) : fd(s.event_start)]);
  if (s.duration) facts.push(["calendar", t("Durée"), s.duration]);
  if (s.city || s.remote) facts.push(["globe", t("Lieu"), s.remote ? t("En ligne") : String(s.city)]);
  const coverage = s.coverage.map((c) => t(COVERAGE[c] ?? c));

  return (
    <div className="mx-auto max-w-6xl space-y-8 [overflow-wrap:anywhere]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href={`/bourses${s.kind && s.kind !== "bourse" ? `?kind=${s.kind}` : ""}`} className="text-sm text-muted hover:text-ink">← {s.kind === "stage" ? t("Tous les stages") : s.kind === "conference" ? t("Toutes les conférences") : t("Toutes les bourses")}</Link>
        <form action="/bourses" className="relative w-full sm:w-80" role="search">
          <Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input name="q" className="input rounded-full py-2 pl-10" placeholder={t("Rechercher une autre bourse")} aria-label={t("Rechercher une bourse")} />
        </form>
      </div>

      <div className="card relative overflow-hidden p-6 sm:p-10">
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-mint/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-1/3 h-48 w-48 rounded-full bg-gold/10 blur-3xl" />
        {s.study_countries.length > 0 && <div className="relative mb-3 flex flex-wrap gap-1.5">{s.study_countries.slice(0, 8).map((c) => <Flag key={c} code={c} className="h-5 w-7" />)}</div>}
        <p className="eyebrow relative">{s.kind && s.kind !== "bourse" ? `${t(s.kind_label ?? s.kind)} · ` : ""}{s.organization}</p>
        <h1 className="relative mt-2 max-w-3xl text-[1.75rem] leading-tight sm:text-4xl lg:text-5xl">{s.title}</h1>
        <p className="accent relative mt-3 text-2xl">{formatAmount(s, lang)}</p>
        <div className="relative mt-4 flex flex-wrap gap-2">
          <DeadlineBadge deadline={s.deadline} s={s} />
          {s.full_funding && <span className="rounded-full bg-ok-soft px-2.5 py-0.5 text-xs font-semibold text-ok">{t("Financement complet")}</span>}
        </div>
        <p className="relative mt-5 max-w-3xl text-muted">{s.summary}</p>
      </div>

      {dl.status === "expiree" && (
        <div className="card flex flex-wrap items-start gap-3 border-danger/40 p-5">
          <Icon name="calendar" className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{t("Les candidatures sont closes pour cette session.")}</p>
            <p className="mt-1 text-sm text-muted">
              {s.next_expected_deadline ? <>{t("Prochaine date limite attendue vers le")} <span className="font-semibold text-ink">{fd(s.next_expected_deadline)}</span>. </> : t("Ce programme rouvre en général à la même période chaque année. ")}
              {t("Vous pouvez préparer votre dossier dès maintenant pour être prêt à l'ouverture.")}
            </p>
          </div>
          <Link href="/bourses" className="btn-ghost">{t("Voir les bourses ouvertes")}</Link>
        </div>
      )}
      {dl.status === "urgente" && (
        <div className="card flex items-start gap-3 border-warm/50 bg-warm-soft p-5">
          <Icon name="calendar" className="mt-0.5 h-5 w-5 shrink-0 text-warm" />
          <p className="text-sm"><span className="font-semibold">{dl.long ?? `Plus que ${dl.days} jour${(dl.days ?? 0) > 1 ? "s" : ""} pour postuler.`}</span> {t("Commencez par les documents qui prennent le plus de temps : relevés certifiés, lettres de recommandation et test de langue.")}</p>
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        <div className="min-w-0 space-y-10">
          <section>
            <p className="eyebrow">{t("Conditions")}</p>
            <h2 className="mt-2 text-xl sm:text-2xl">{t("Qui peut postuler")}</h2>
            <ul className="mt-4 space-y-2">
              {conds.map((c) => (
                <li key={c} className="card flex gap-3 px-4 py-3 text-sm">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand-soft text-brand"><Icon name="check" className="h-3 w-3" /></span>
                  {c}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted">{t("Toutes les conditions doivent être remplies le jour de la candidature.")}</p>
          </section>

          {coverage.length > 0 && (
            <section>
              <p className="eyebrow">{t("Financement")}</p>
              <h2 className="mt-2 text-xl sm:text-2xl">{t("Ce que la bourse prend en charge")}</h2>
              <div className="mt-4 flex flex-wrap gap-2">
                {coverage.map((c) => <span key={c} className="rounded-full border border-line bg-card px-3.5 py-1.5 text-sm">{c}</span>)}
              </div>
            </section>
          )}

          {docs.length > 0 && (
            <section>
              <p className="eyebrow">{t("Dossier")}</p>
              <h2 className="mt-2 text-xl sm:text-2xl">{t("Documents à fournir")}</h2>
              <ol className="mt-4 grid gap-3 sm:grid-cols-2">
                {docs.map((d, i) => (
                  <li key={d.label} className="card p-4">
                    <p className="flex items-center gap-2 font-semibold"><span className="font-mono text-xs text-brand">{String(i + 1).padStart(2, "0")}</span>{d.label}</p>
                    {d.detail && <p className="mt-1.5 text-sm text-muted">{d.detail}</p>}
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>

        <aside className="min-w-0 space-y-4 lg:sticky lg:top-24">
          <div className="card p-5">
            <dl className="space-y-3">
              {facts.map(([icon, k, v]) => (
                <div key={k} className="flex gap-3">
                  <Icon name={icon} className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                  <div><dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{k}</dt><dd className="text-sm">{v}</dd></div>
                </div>
              ))}
            </dl>
            <a href={url} target="_blank" rel="noopener noreferrer" className={`${dl.status === "expiree" ? "btn-ghost" : "btn-primary"} mt-5 w-full`}>
              {dl.status === "expiree" ? t("Voir la page officielle") : t("Postuler sur le site officiel")} <Icon name="arrow" className="h-4 w-4 -rotate-45" />
            </a>
            {link && <p className={`mt-2 text-xs ${link.cls}`}>{t(link.t)}{s.link_checked_at ? ` · ${fd(s.link_checked_at)}` : ""}</p>}
            <p className="mt-2 truncate text-[11px] text-muted" title={url}>{url.replace(/^https?:\/\//, "")}</p>
          </div>
          <div className="relative overflow-hidden rounded-2xl bg-night p-5 text-white">
            <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-mint/25 blur-2xl" />
            <p className="relative font-semibold">{t("Besoin d'aide pour ce dossier ?")}</p>
            <p className="relative mt-1 text-sm text-white/65">{t("Un expert relit vos documents et vous prépare à l'entretien, dès 15 000 F CFA.")}</p>
            <Link href={`/accompagnement?offre=standard&bourse=${s.id}`} className="btn-primary relative mt-4 w-full">{t("Être accompagné")}</Link>
          </div>
          <DetailActions s={s} />
          <ScholarshipTools s={s} />
        </aside>
      </div>

      <section id="postuler" className="scroll-mt-24 rounded-3xl border border-line bg-card p-6 sm:p-10">
        <p className="eyebrow">{t("Comment postuler")}</p>
        <h2 className="mt-2 text-[1.65rem] sm:text-3xl">{t("Les étapes,")} <span className="accent">{t("dans l'ordre.")}</span></h2>
        <ol className="mt-8 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {steps.map((t, i) => (
            <li key={i} className="relative pl-12">
              <span className="absolute left-0 top-0 grid h-9 w-9 place-items-center rounded-full border border-brand/40 bg-brand-soft font-mono text-xs text-brand">{String(i + 1).padStart(2, "0")}</span>
              <p className="text-sm leading-relaxed [overflow-wrap:anywhere]">{t}</p>
            </li>
          ))}
          <li className="relative pl-12">
            <span className="absolute left-0 top-0 grid h-9 w-9 place-items-center rounded-full bg-mint text-[#04140e]"><Icon name="arrow" className="h-4 w-4 -rotate-45" /></span>
            <p className="text-sm leading-relaxed">{t("Le formulaire officiel est ici :")} <a href={url} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand underline-offset-2 hover:underline">{s.organization}</a>.</p>
          </li>
        </ol>
      </section>

      <AdvisorBanner scholarshipId={s.id} />
    </div>
  );
}
