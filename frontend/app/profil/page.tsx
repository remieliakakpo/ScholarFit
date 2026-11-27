"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import AccountCard from "@/components/AccountCard";
import CountryPicker from "@/components/CountryPicker";
import Icon from "@/components/Icon";
import RequireAuth from "@/components/RequireAuth";
import { ScoreRing } from "@/components/ScholarshipCard";
import { Meta, Profile, api, getMeta, normalizeProfile, setToken } from "@/lib/api";
import { useT } from "@/components/LangProvider";

const STEPS = ["Identité", "Parcours", "Projet et atouts", "Facultatif"];
const SITUATIONS: Record<string, string> = {
  revenus_modestes: "Revenus familiaux modestes",
  premiere_generation: "Première génération à l'université",
  refugie: "Statut de réfugié",
  handicap: "Situation de handicap",
  femmes: "Je suis une femme (bourses réservées)",
};
const TESTS = ["IELTS", "TOEFL", "DELF", "DALF", "TCF", "TestDaF"];

function ProfileForm() {
  const { t } = useT();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [p, setP] = useState<Profile | null>(null);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [langText, setLangText] = useState("");

  useEffect(() => {
    getMeta().then(setMeta).catch((e) => setError(e.message));
    api<unknown>("/api/profile").then((raw) => {
      const pr = normalizeProfile(raw);
      setP(pr);
      setLangText(Object.entries(pr.languages).map(([k, v]) => `${k}:${v}`).join(", "));
    }).catch((e) => setError(e.message));
  }, []);

  if (!p || !meta)
    return error ? (
      <div className="card mx-auto max-w-md p-8 text-center">
        <p className="font-serif text-xl">{t("Impossible d'afficher votre profil pour le moment.")}</p>
        <p className="mt-2 text-sm text-muted">{error}</p>
        <button className="btn-primary mt-5" onClick={() => window.location.reload()}>{t("Réessayer")}</button>
      </div>
    ) : <p className="text-muted">{t("Chargement…")}</p>;
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v });

  async function save(goNext = false) {
    if (!p) return;
    setSaving(true);
    setError(null);
    setMsg(null);
    const languages = Object.fromEntries(langText.split(",").map((x) => x.split(":").map((s) => s.trim())).filter((x) => x[0]).map(([k, v]) => [k.toLowerCase(), v || "?"]));
    const body = {
      full_name: p.full_name || null, birth_date: p.birth_date || null, nationalities: p.nationalities,
      residence_country: p.residence_country || null, phone: p.phone || null, alerts_opt_in: p.alerts_opt_in,
      current_level: p.current_level || null, target_level: p.target_level || null, domain: p.domain || null,
      institution: p.institution || null, grade_average: p.grade_average, wished_countries: p.wished_countries,
      languages, language_scores: p.language_scores, experiences: p.experiences || null, engagement: p.engagement || null, interests: p.interests || null, work_experience_years: p.work_experience_years ?? null,
      project: p.project || null, full_funding_only: p.full_funding_only, situations: p.situations,
    };
    try {
      const out = normalizeProfile(await api<unknown>("/api/profile", { method: "PUT", body: JSON.stringify(body) }));
      setP(out);
      setMsg(t("Profil enregistré."));
      if (goNext) setStep(Math.min(step + 1, STEPS.length - 1));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function uploadCV(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    setError(null);
    try {
      const out = normalizeProfile(await api<unknown>("/api/profile/cv", { method: "POST", body: fd }));
      setP(out);
      setMsg(t("CV importé : vérifiez les champs préremplis (expériences, engagement, domaine)."));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function deleteAccount() {
    if (!confirm(t("Supprimer définitivement votre compte, votre profil, vos CV, lettres et candidatures ?"))) return;
    await api("/api/auth/me", { method: "DELETE" });
    setToken(null);
    window.location.href = "/";
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-5">
      <div>
        <h1 className="text-[1.65rem] sm:text-3xl">{t("Mon profil")}</h1>
        <p className="mt-1 flex items-center gap-2 text-sm text-muted"><Icon name="shield" className="h-4 w-4 text-ok" />{t("Vos données sont privées : elles servent uniquement au matching de vos bourses.")}</p>
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-line">
        {STEPS.map((s, i) => (
          <button key={s} onClick={() => setStep(i)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm ${i === step ? "border-brand font-semibold text-ink" : "border-transparent text-muted hover:text-ink"}`}>{t(s)}</button>
        ))}
      </div>
      <div className="card space-y-4 p-6">
        {step === 0 && (
          <>
            <div><label className="label">{t("Nom complet")}</label><input className="input" name="name" autoComplete="name" value={p.full_name ?? ""} onChange={(e) => set("full_name", e.target.value)} /></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><label className="label">{t("Date de naissance *")}</label><input type="date" name="bday" autoComplete="bday" className="input" value={p.birth_date ?? ""} onChange={(e) => set("birth_date", e.target.value)} /></div>
              <div><label className="label">{t("Pays de résidence")}</label>
                <select className="input" name="country" autoComplete="country" value={p.residence_country ?? ""} onChange={(e) => set("residence_country", e.target.value)}>
                  <option value="">{t("Choisir…")}</option>{Object.entries(meta.countries).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select></div>
            </div>
            <div><label className="label">{t("Nationalité(s) *")}</label><CountryPicker value={p.nationalities} onChange={(v) => set("nationalities", v)} countries={meta.countries} placeholder={t("Ajouter une nationalité")} /></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><label className="label">{t("WhatsApp (alertes, facultatif)")}</label><input type="tel" name="tel" autoComplete="tel" inputMode="tel" className="input" value={p.phone ?? ""} onChange={(e) => set("phone", e.target.value)} placeholder="+221…" /></div>
              <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={p.alerts_opt_in} onChange={(e) => set("alerts_opt_in", e.target.checked)} />{t("Recevoir les alertes (nouvelles bourses, rappels)")}</label>
            </div>
          </>
        )}
        {step === 1 && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><label className="label">{t("Niveau actuel")}</label>
                <select className="input" value={p.current_level ?? ""} onChange={(e) => set("current_level", e.target.value)}>
                  <option value="">{t("Choisir…")}</option>{Object.entries(meta.levels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select></div>
              <div><label className="label">{t("Niveau visé (diplôme à financer) *")}</label>
                <select className="input" value={p.target_level ?? ""} onChange={(e) => set("target_level", e.target.value)}>
                  <option value="">{t("Choisir…")}</option>{Object.entries(meta.levels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select></div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><label className="label">{t("Domaine d'études *")}</label>
                <select className="input" value={p.domain ?? ""} onChange={(e) => set("domain", e.target.value)}>
                  <option value="">{t("Choisir…")}</option>{Object.entries(meta.domains).filter(([k]) => k !== "tous").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select></div>
              <div><label className="label">{t("Moyenne (sur 20)")}</label><input type="number" step="0.1" min={0} max={20} className="input" value={p.grade_average ?? ""} onChange={(e) => set("grade_average", e.target.value === "" ? null : Number(e.target.value))} /></div>
            </div>
            <div><label className="label">{t("Établissement actuel")}</label><input className="input" name="organization" autoComplete="organization" value={p.institution ?? ""} onChange={(e) => set("institution", e.target.value)} /></div>
          </>
        )}
        {step === 2 && (
          <>
            <div><label className="label">{t("Pays où vous souhaitez étudier")}</label>
              <CountryPicker value={p.wished_countries} onChange={(v) => set("wished_countries", v)} countries={meta.countries} placeholder={t("Ajouter un pays (vide = tous)")} />
              <p className="mt-1 text-xs text-muted">{t("Si vous choisissez des pays, nous excluons les bourses limitées à d'autres pays.")}</p></div>
            <div><label className="label">{t("Langues parlées")}</label><input className="input" value={langText} onChange={(e) => setLangText(e.target.value)} placeholder={t("fr:natif, en:B2, de:A2")} /></div>
            <div><label className="label">{t("Scores de tests de langue")}</label>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {TESTS.map((t) => (
                  <label key={t} className="flex items-center gap-2 text-sm">
                    <span className="w-16 text-muted">{t}</span>
                    <input type="number" step="0.5" className="input" value={p.language_scores[t] ?? ""} onChange={(e) => {
                      const ls = { ...p.language_scores };
                      if (e.target.value === "") delete ls[t]; else ls[t] = Number(e.target.value);
                      set("language_scores", ls);
                    }} />
                  </label>
                ))}
              </div>
              <p className="mt-1 text-xs text-muted">DELF/DALF : indique le niveau en chiffre (B1 = 1, B2 = 2, C1 = 3).</p></div>
            <div><label className="label">{t("Expériences (stages, emplois, projets)")}</label><textarea rows={4} className="input" value={p.experiences ?? ""} onChange={(e) => set("experiences", e.target.value)} /></div>
            <div><label className="label">{t("Engagement associatif")}</label><textarea rows={3} className="input" value={p.engagement ?? ""} onChange={(e) => set("engagement", e.target.value)} /></div>
            <div><label className="label">{t("Centres d'intérêt")}</label><input className="input" placeholder={t("Ex. robotique éducative, football, lecture d'essais économiques")} value={p.interests ?? ""} onChange={(e) => set("interests", e.target.value)} /></div>
            <div><label className="label">{t("Années d'expérience professionnelle (stages et emplois)")}</label><input type="number" min={0} max={60} step={0.5} className="input" value={p.work_experience_years ?? ""} onChange={(e) => set("work_experience_years", e.target.value === "" ? null : Number(e.target.value))} /></div>
            <div><label className="label">{t("Projet professionnel")}</label><textarea rows={3} className="input" value={p.project ?? ""} onChange={(e) => set("project", e.target.value)} placeholder={t("Ce que vous voulez faire après vos études, et pourquoi.")} /></div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={p.full_funding_only} onChange={(e) => set("full_funding_only", e.target.checked)} />{t("Je ne cherche que des bourses à financement complet")}</label>
          </>
        )}
        {step === 3 && (
          <>
            <p className="text-sm text-muted">{t("Ces informations sont facultatives et ne sont jamais partagées. Elles débloquent des bourses réservées à certains publics.")}</p>
            {Object.entries(SITUATIONS).map(([k, v]) => (
              <label key={k} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={p.situations.includes(k)} onChange={(e) => set("situations", e.target.checked ? [...p.situations, k] : p.situations.filter((x) => x !== k))} />{t(v)}
              </label>
            ))}
          </>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {msg && <p className="text-sm text-brand">{msg}</p>}
        <div className="flex flex-wrap gap-2 pt-2">
          <button className="btn-primary" disabled={saving} onClick={() => save(step < STEPS.length - 1)}>{step < STEPS.length - 1 ? t("Enregistrer et continuer") : t("Enregistrer")}</button>
          {step > 0 && <button className="btn-ghost" onClick={() => setStep(step - 1)}>{t("Retour")}</button>}
        </div>
      </div>

      </div>

      <aside className="space-y-4">
        <div className={`card p-5 ${p.minimum_ok ? "border-ok/40" : ""}`}>
          <div className="flex items-center gap-4">
            <span className="rounded-full bg-night p-1"><ScoreRing value={p.completeness} color={p.minimum_ok ? "#3ee0a8" : "#ffb547"} size={60} /></span>
            <div>
              <p className="font-semibold">{p.minimum_ok ? t("Votre profil permet le matching") : t("Profil à compléter")}</p>
              <p className="text-xs text-muted">{t("Complété à")} {p.completeness} %</p>
            </div>
          </div>
          {!p.minimum_ok && p.missing_minimum.length > 0 && <p className="mt-3 text-sm text-warm">{t("Il manque :")} {p.missing_minimum.join(", ")}</p>}
          {p.completeness_tip && <p className="mt-2 text-xs text-muted">{p.completeness_tip}</p>}
          {p.minimum_ok && <Link href="/mes-bourses" className="btn-dark mt-4 w-full">{t("Voir mes bourses")}</Link>}
        </div>

        <div className="card p-5">
          <p className="flex items-center gap-2 text-sm font-semibold"><Icon name="upload" className="h-4 w-4 text-brand" />{t("Importez votre CV")}</p>
          <p className="mt-1 text-xs text-muted">{t("PDF texte, Word (.docx) ou .txt. Seuls les champs vides sont préremplis, vous vérifiez ensuite.")}</p>
          <label className="btn-ghost mt-3 w-full cursor-pointer">
            {t("Choisir un fichier")}
            <input type="file" accept=".pdf,.docx,.txt" className="sr-only" onChange={(e) => e.target.files?.[0] && uploadCV(e.target.files[0])} />
          </label>
          {p.has_cv && <p className="mt-2 text-xs text-ok">{t("✓ Un CV est enregistré.")} <Link href="/cv" className="underline">{t("L'améliorer")}</Link></p>}
        </div>

        <AccountCard />

        <button className="w-full text-center text-xs text-danger hover:underline" onClick={deleteAccount}>{t("Supprimer mon compte et toutes mes données")}</button>
      </aside>
    </div>
  );
}

export default function Page() {
  return <RequireAuth><ProfileForm /></RequireAuth>;
}
