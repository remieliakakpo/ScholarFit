// Page rendue côté serveur : elle peut être indexée par les moteurs de recherche.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DeadlineBadge } from "@/components/ScholarshipCard";
import Flag from "@/components/Flag";
import Icon from "@/components/Icon";
import Offers from "@/components/Offers";
import DetailActions from "@/components/DetailActions";
import { applyUrl, deadlineInfo, formatAmount, formatDate } from "@/lib/api";
import { COVERAGE, DEFAULT_STEPS, LINK, conditions, documents, loadScholarship } from "@/lib/scholarship-detail";
import { getT } from "@/lib/i18n-server";
import { countryName } from "@/lib/i18n";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { t, lang } = await getT();
  const data = await loadScholarship((await params).id, lang);
  return data ? { title: data.s.title, description: data.s.summary } : { title: t("Bourse introuvable") };
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { t, lang } = await getT();
  const data = await loadScholarship((await params).id, lang);
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
            {dl.status === "expiree" ? (
              <a href={url} target="_blank" rel="noopener noreferrer" className="btn-ghost mt-5 w-full">
                {t("Voir la page officielle")} <Icon name="arrow" className="h-4 w-4 -rotate-45" />
              </a>
            ) : (
              <Link href={`/postuler/${s.id}`} className="btn-primary mt-5 w-full">
                {t("Postuler")} <Icon name="arrow" className="h-4 w-4" />
              </Link>
            )}
            {link && <p className={`mt-2 text-xs ${link.cls}`}>{t(link.t)}{s.link_checked_at ? ` · ${fd(s.link_checked_at.slice(0, 10))}` : ""}</p>}
            {(() => {
              const last = [s.verified_at, s.link_checked_at, s.collected_at].filter(Boolean).map((d) => (d as string).slice(0, 10)).sort().pop();
              return last ? <p className="mt-1 text-[11px] text-muted">{t("Fiche mise à jour le {d}", { d: fd(last) })}</p> : null;
            })()}
            <p className="mt-2 truncate text-[11px] text-muted" title={url}>{url.replace(/^https?:\/\//, "")}</p>
          </div>
          <div className="relative overflow-hidden rounded-2xl bg-night p-5 text-white">
            <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-mint/25 blur-2xl" />
            <p className="relative font-semibold">{t("Besoin d'aide pour ce dossier ?")}</p>
            <p className="relative mt-1 text-sm text-white/65">{t("Un expert prépare votre dossier et dépose votre candidature, dès 15 000 F CFA.")}</p>
            <Link href={`/accompagnement?offre=standard&bourse=${s.id}`} className="btn-primary relative mt-4 w-full">{t("Être accompagné")}</Link>
          </div>
          <DetailActions s={s} />
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

      <section>
        <p className="eyebrow">{t("Tarifs")}</p>
        <h2 className="mt-2 text-[1.65rem] sm:text-3xl">{t("Postulez seul ou faites-vous")} <span className="accent">{t("accompagner.")}</span></h2>
        <p className="mt-2 max-w-2xl text-muted">{t("Postuler vous-même est gratuit. Si vous souhaitez qu'un expert relise votre dossier et vous prépare, choisissez une formule.")}</p>
        <div className="mt-6"><Offers scholarshipId={s.id} /></div>
      </section>
    </div>
  );
}
