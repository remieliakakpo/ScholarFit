"use client";
import { useT } from "@/components/LangProvider";
import { CVData, CVEntry } from "@/lib/docs";
import Editable from "./Editable";

const ACCENT = "#1F3A5F";

/** Aperçu fidèle du CV (mêmes rubriques et même disposition que le PDF), modifiable sur place. */
export default function PaperCV({ cv, editable, onChange }: { cv: CVData; editable: boolean; onChange: (cv: CVData) => void }) {
  const { t } = useT();
  const h = cv.header;
  const centered = cv.layout !== "dated"; // modèle ATS : en-tête centré, comme le PDF
  const dated = cv.layout === "dated";
  const en = cv.language === "en";
  const setHeader = (k: keyof CVData["header"], v: string) => onChange({ ...cv, header: { ...h, [k]: v } });
  const setEntry = (si: number, ei: number, patch: Partial<CVEntry>) => {
    const sections = cv.sections.map((s, i) => i !== si ? s : { ...s, entries: s.entries.map((e, j) => (j !== ei ? e : { ...e, ...patch })) });
    onChange({ ...cv, sections });
  };
  const setItem = (si: number, ii: number, v: string) => {
    const sections = cv.sections.map((s, i) => i !== si ? s : { ...s, items: s.items.map((x, j) => (j === ii ? v : x)).filter((x) => x.trim()) });
    onChange({ ...cv, sections });
  };
  const setBullet = (si: number, ei: number, bi: number, v: string) => {
    const e = cv.sections[si].entries[ei];
    setEntry(si, ei, { bullets: e.bullets.map((b, j) => (j === bi ? v : b)).filter((b) => b.trim()) });
  };
  const contact = (["location", "phone", "email", "links"] as const).filter((k) => h[k] || editable);

  const SectionTitle = ({ children }: { children: React.ReactNode }) => (
    <h3 className="mt-5 border-b pb-0.5 [font-family:inherit] text-[12.5px] font-bold uppercase tracking-[0.04em]" style={{ color: ACCENT, borderColor: ACCENT, fontFamily: "inherit", letterSpacing: "0.04em" }}>{children}</h3>
  );

  return (
    <article
      className="mx-auto w-full max-w-[794px] bg-white px-5 py-7 text-[13px] leading-[1.42] text-[#1a1a1a] shadow-[0_24px_60px_-28px_rgba(0,0,0,0.55)] ring-1 ring-black/5 sm:px-12 sm:py-12 sm:text-[13.5px]"
      style={{ fontFamily: "Calibri, Carlito, 'Segoe UI', Arial, sans-serif" }}
    >
      <header className={centered ? "text-center" : ""}>
        <Editable as="h2" editable={editable} value={h.name} onChange={(v) => setHeader("name", v)} placeholder={t("Nom complet")}
          className={`block text-[24px] font-bold leading-tight tracking-normal [font-family:inherit] text-[#111] sm:text-[27px] ${centered ? "uppercase" : ""}`} />
        {(h.headline || editable) && (
          <Editable as="p" editable={editable} value={h.headline} onChange={(v) => setHeader("headline", v)} placeholder={t("Titre du CV")}
            className="mt-0.5 block text-[13px] font-bold uppercase tracking-[0.02em] text-[#1F3A5F] sm:text-[14px]" />
        )}
        <p className={`mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[12px] text-[#555] ${centered ? "justify-center" : ""}`}>
          {contact.map((k, i) => (
            <span key={k} className="inline-flex items-center gap-2">
              {i > 0 && <span aria-hidden>|</span>}
              <Editable editable={editable} value={h[k]} onChange={(v) => setHeader(k, v)} placeholder={t({ email: "E-mail", phone: "Téléphone", location: "Ville, pays", links: "LinkedIn, portfolio" }[k])} />
            </span>
          ))}
        </p>
        {(h.objective || editable) && (
          <Editable as="p" editable={editable} value={h.objective ?? ""} onChange={(v) => setHeader("objective", v)} placeholder={t("Candidature, rentrée et mobilité")}
            className="block text-[12px] text-[#555]" />
        )}
        {(h.birth_date || h.nationality) && (
          <p className={`text-[12px] text-[#555] ${centered ? "text-center" : ""}`}>
            {[h.birth_date && `${en ? "Date of birth" : "Date de naissance"} ${h.birth_date}`, h.nationality && `${en ? "Nationality" : "Nationalité"} ${h.nationality}`].filter(Boolean).join("  |  ")}
          </p>
        )}
      </header>

      {(cv.summary || editable) && (
        <section>
          <SectionTitle>{cv.summary_title}</SectionTitle>
          <Editable as="p" multiline editable={editable} value={cv.summary} onChange={(v) => onChange({ ...cv, summary: v })} placeholder={t("Deux ou trois phrases sur votre projet d'études")} className="mt-1.5 block" />
        </section>
      )}

      {cv.sections.map((sec, si) => (
        <section key={sec.key + si}>
          <SectionTitle>{sec.title}</SectionTitle>
          {sec.kind === "list" ? (
            <div className="mt-1.5 space-y-0.5">
              {sec.items.map((it, ii) => {
                const m = !editable && sec.key === "skills" ? /^([^:]{2,60}?)\s?:\s(.+)$/.exec(it) : null;
                return m && m[1].split(" ").length <= 5
                  ? <p key={ii}><strong>{m[1]} :</strong> {m[2]}</p>
                  : <Editable key={ii} as="p" editable={editable} value={it} onChange={(v) => setItem(si, ii, v)} className="block" />;
              })}
            </div>
          ) : (
            <div className="mt-2 space-y-3">
              {sec.entries.map((e, ei) => {
                const title = <Editable as="p" editable={editable} value={e.title} onChange={(v) => setEntry(si, ei, { title: v })} className="block font-bold" />;
                const org = (e.organization || e.location || editable) ? (
                  <p className="italic text-[#555]">
                    <Editable editable={editable} value={e.organization} onChange={(v) => setEntry(si, ei, { organization: v })} placeholder={t("Établissement ou organisme")} />
                    {e.location && <>, <Editable editable={editable} value={e.location} onChange={(v) => setEntry(si, ei, { location: v })} /></>}
                  </p>
                ) : null;
                const bullets = e.bullets.length > 0 ? (
                  <ul className="mt-0.5 list-disc space-y-0.5 pl-5 marker:text-[#444]">
                    {e.bullets.map((b, bi) => <Editable key={bi} as="li" editable={editable} value={b} onChange={(v) => setBullet(si, ei, bi, v)} />)}
                  </ul>
                ) : null;
                const dates = <Editable as="p" editable={editable} value={e.dates} onChange={(v) => setEntry(si, ei, { dates: v })} placeholder={t("Dates")} className="block shrink-0 text-[#555]" />;
                if (dated)
                  return (
                    <div key={ei} className="grid grid-cols-[88px_1fr] gap-3 sm:grid-cols-[132px_1fr]">
                      {dates}
                      <div className="min-w-0">{title}{org}{bullets}</div>
                    </div>
                  );
                // Modèle ATS : « Poste | Organisme | Lieu » sur une ligne, dates à droite
                const showHead = editable || e.title || e.organization || e.location || e.dates;
                return (
                  <div key={ei}>
                    {showHead && (
                      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                        <p className="min-w-0 flex-1">
                          <Editable editable={editable} value={e.title} onChange={(v) => setEntry(si, ei, { title: v })} placeholder={t("Poste ou diplôme")} className="font-bold" />
                          {(e.organization || editable) && <> <span className="text-[#555]">|</span> <Editable editable={editable} value={e.organization} onChange={(v) => setEntry(si, ei, { organization: v })} placeholder={t("Établissement ou organisme")} /></>}
                          {(e.location || editable) && <> <span className="text-[#555]">|</span> <Editable editable={editable} value={e.location} onChange={(v) => setEntry(si, ei, { location: v })} placeholder={t("Lieu")} /></>}
                        </p>
                        {dates}
                      </div>
                    )}
                    {bullets}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ))}

      {cv.signature && (
        <footer className="mt-10 text-[13px]">
          <Editable as="p" editable={editable} value={cv.signature} onChange={(v) => onChange({ ...cv, signature: v })} className="block" />
          <p>{h.name}</p>
        </footer>
      )}
    </article>
  );
}
