// Page de candidature : tout ce qu'il faut savoir avant de postuler, puis le lien officiel
// ou l'accompagnement par un expert. Rendue côté serveur, aucun compte n'est demandé ici.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DeadlineBadge } from "@/components/ScholarshipCard";
import Icon from "@/components/Icon";
import Offers from "@/components/Offers";
import { applyUrl, deadlineInfo, formatAmount, formatDate } from "@/lib/api";
import { COVERAGE, DEFAULT_STEPS, LINK, conditions, documents, loadScholarship } from "@/lib/scholarship-detail";
import { getT } from "@/lib/i18n-server";
import { countryName } from "@/lib/i18n";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { t, lang } = await getT();
  const data = await loadScholarship((await params).id, lang);
  return data ? { title: t("Postuler : {title}", { title: data.s.title }), description: data.s.summary } : { title: t("Bourse introuvable") };
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="relative pl-12 sm:pl-14">
      <span className="absolute left-0 top-0 grid h-9 w-9 place-items-center rounded-full border border-brand/40 bg-brand-soft font-mono text-xs text-brand">{String(n).padStart(2, "0")}</span>
      <h2 className="pt-1 text-xl sm:text-2xl">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { t, lang } = await getT();
  const data = await loadScholarship((await params).id, lang);
  if (!data) notFound();
  const { s, meta } = data;
  const dl = deadlineInfo(s, lang);
  const closed = dl.status === "expiree";
  const conds = conditions(s, meta, t, lang);
  const docs = documents(s, meta, t);
  const steps = s.application_steps?.length ? s.application_steps : DEFAULT_STEPS.map((x) => t(x));
  const coverage = s.coverage.map((c) => t(COVERAGE[c] ?? c));
  const url = applyUrl(s);
  const link = s.link_status ? LINK[s.link_status] : undefined;
  const fd = (d: string | null) => formatDate(d, lang);
  const facts: [string, string, string][] = [
    ["medal", t("Financement"), formatAmount(s, lang)],
    ["calendar", t("Date limite"), s.deadline ? fd(s.deadline) : t("Variable selon le programme")],
    ["cap", t("Niveaux"), s.levels.map((l) => t(meta.levels[l] ?? l).split(" : ").pop()).join(" · ") || t("Non précisé")],
    ["globe", t("Pays d'études"), s.study_countries.map((c) => countryName(c, lang, meta.countries[c])).join(", ") || t("Plusieurs pays")],
  ];
  let n = 0;

  return (
    <div className="mx-auto max-w-4xl space-y-10 [overflow-wrap:anywhere]">
      <Link href={`/bourses/${s.id}`} className="text-sm text-muted hover:text-ink">← {t("Retour à la fiche")}</Link>

      <header className="card relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-mint/15 blur-3xl" />
        <p className="eyebrow relative">{t("Candidature")} · {s.organization}</p>
        <h1 className="relative mt-2 text-[1.6rem] leading-tight sm:text-4xl">{s.title}</h1>
        <div className="relative mt-4 flex flex-wrap gap-2">
          <DeadlineBadge deadline={s.deadline} s={s} />
          {s.full_funding && <span className="rounded-full bg-ok-soft px-2.5 py-0.5 text-xs font-semibold text-ok">{t("Financement complet")}</span>}
        </div>
        <dl className="relative mt-6 grid gap-4 sm:grid-cols-2">
          {facts.map(([icon, k, v]) => (
            <div key={k} className="flex gap-3">
              <Icon name={icon} className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
              <div><dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{k}</dt><dd className="text-sm">{v}</dd></div>
            </div>
          ))}
        </dl>
        {s.summary && <p className="relative mt-6 text-muted">{s.summary}</p>}
      </header>

      {closed && (
        <div className="card flex items-start gap-3 border-danger/40 p-5">
          <Icon name="calendar" className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
          <p className="text-sm">
            <span className="font-semibold">{t("Les candidatures sont closes pour cette session.")}</span>{" "}
            {s.next_expected_deadline ? <>{t("Prochaine date limite attendue vers le")} <span className="font-semibold">{fd(s.next_expected_deadline)}</span>. </> : null}
            {t("Vous pouvez préparer votre dossier dès maintenant pour être prêt à l'ouverture.")}
          </p>
        </div>
      )}

      <div className="space-y-10">
        <Step n={++n} title={t("Vérifiez les conditions")}>
          <ul className="space-y-2">
            {conds.map((c) => (
              <li key={c} className="card flex gap-3 px-4 py-3 text-sm">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand-soft text-brand"><Icon name="check" className="h-3 w-3" /></span>
                {c}
              </li>
            ))}
          </ul>
          {coverage.length > 0 && !conds.some((c) => /couvert|cover/i.test(c)) && (
            <p className="mt-4 text-sm text-muted">
              <span className="font-semibold text-ink">{t("Ce que la bourse prend en charge :")}</span> {coverage.join(", ")}.
            </p>
          )}
        </Step>

        {docs.length > 0 && (
          <Step n={++n} title={t("Rassemblez les pièces à fournir")}>
            <ol className="grid gap-3 sm:grid-cols-2">
              {docs.map((d, i) => (
                <li key={d.label} className="card p-4">
                  <p className="flex items-center gap-2 font-semibold"><span className="font-mono text-xs text-brand">{String(i + 1).padStart(2, "0")}</span>{d.label}</p>
                  {d.detail && <p className="mt-1.5 text-sm text-muted">{d.detail}</p>}
                </li>
              ))}
            </ol>
            <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-brand/40 bg-brand-soft/40 p-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm">
                <span className="font-semibold">{t("CV et lettre adaptés à cette bourse.")}</span>{" "}
                <span className="text-muted">{t("Votre premier dossier est offert, ensuite l'abonnement est à 2 500 F CFA par mois.")}</span>
              </p>
              <div className="flex shrink-0 gap-2">
                <Link href={`/cv?bourse=${s.id}`} className="btn-ghost px-4 py-2 text-xs">{t("Adapter mon CV")}</Link>
                <Link href={`/lettre/${s.id}`} className="btn-ghost px-4 py-2 text-xs">{t("Rédiger ma lettre")}</Link>
              </div>
            </div>
          </Step>
        )}

        <Step n={++n} title={t("Suivez les étapes de candidature")}>
          <ol className="space-y-3">
            {steps.map((x, i) => (
              <li key={i} className="flex gap-3 text-sm leading-relaxed">
                <span className="w-6 shrink-0 font-mono text-xs leading-6 text-brand">{String(i + 1).padStart(2, "0")}</span>
                <span>{x}</span>
              </li>
            ))}
          </ol>
        </Step>
      </div>

      <section id="lien-officiel" className="scroll-mt-24 rounded-3xl border border-line bg-card p-6 sm:p-10">
        <p className="eyebrow">{t("Dernière étape")}</p>
        <h2 className="mt-2 text-[1.65rem] sm:text-3xl">{t("Envoyez votre candidature")} <span className="accent">{t("sur le site officiel.")}</span></h2>
        <p className="mt-2 max-w-2xl text-muted">{t("Le formulaire se remplit directement chez {org}. Postuler vous-même est gratuit.", { org: s.organization })}</p>
        <a href={url} target="_blank" rel="noopener noreferrer" className={`${closed ? "btn-ghost" : "btn-primary"} mt-6 w-full sm:w-auto`}>
          {closed ? t("Voir la page officielle") : t("Postuler sur le site officiel")} <Icon name="ext" className="h-4 w-4" />
        </a>
        <p className="mt-3 truncate text-xs text-muted" title={url}>{url.replace(/^https?:\/\//, "")}</p>
        {link && <p className={`mt-1 text-xs ${link.cls}`}>{t(link.t)}</p>}
      </section>

      <section id="accompagnement">
        <p className="eyebrow">{t("Accompagnement")}</p>
        <h2 className="mt-2 text-[1.65rem] sm:text-3xl">{t("Me faire accompagner")} <span className="accent">{t("par un expert.")}</span></h2>
        <p className="mt-2 max-w-2xl text-muted">{t("Un expert ScholarFit prépare votre CV et votre lettre, vérifie chaque pièce, dépose lui-même votre candidature à cette bourse et vous transmet la preuve de dépôt. Un compte vous sera demandé pour démarrer.")}</p>
        <div className="mt-6"><Offers scholarshipId={s.id} only={["standard", "premium"]} /></div>
      </section>
    </div>
  );
}
