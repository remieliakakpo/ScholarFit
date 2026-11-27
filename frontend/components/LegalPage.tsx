import Link from "next/link";

export type Section = { h: string; p: (string | string[])[] };

/** Mise en page commune des pages À propos, Conditions d'utilisation et Confidentialité. */
export default function LegalPage({ eyebrow, title, intro, updated, sections, links }: {
  eyebrow: string; title: string; intro: string; updated?: string; sections: Section[]; links: [string, string][];
}) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-16">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="mt-3 text-3xl leading-tight sm:text-4xl">{title}</h1>
      <p className="mt-4 text-base text-muted sm:text-lg">{intro}</p>
      {updated && <p className="mt-2 text-xs text-muted">{updated}</p>}
      <nav className="mt-8 flex flex-wrap gap-2" aria-label="Pages">
        {links.map(([href, label]) => <Link key={href} href={href} className="chip hover:border-brand hover:text-brand">{label}</Link>)}
      </nav>
      <div className="mt-10 space-y-10">
        {sections.map((s, i) => (
          <section key={s.h} aria-labelledby={`s${i}`}>
            <h2 id={`s${i}`} className="text-xl sm:text-2xl">{s.h}</h2>
            <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-ink/90">
              {s.p.map((x, j) => Array.isArray(x) ? (
                <ul key={j} className="list-disc space-y-1.5 pl-5 marker:text-brand">{x.map((li) => <li key={li}>{li}</li>)}</ul>
              ) : <p key={j}>{x}</p>)}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}
