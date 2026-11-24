"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Offers from "@/components/Offers";
import CoachingWorkspace from "@/components/CoachingWorkspace";
import Icon from "@/components/Icon";
import RequireAuth from "@/components/RequireAuth";
import { Application, Coaching, CoachingDetail, CoachingMeta, DEFAULT_OFFERS, Offer, Scholarship, api, formatDate, getCoachingMeta, getOffers } from "@/lib/api";
import { useT } from "@/components/LangProvider";

const NEEDS_CARDS = [
  { icon: "search", t: "Choisir mes bourses", d: "Nous partons de votre profil et de votre calendrier pour retenir les bourses les plus adaptées.", needs: ["choix_bourses"] },
  { icon: "file", t: "Faire relire mon dossier", d: "CV, lettre, recommandations : un retour précis avant d'envoyer.", needs: ["cv", "lettre", "recommandations"] },
  { icon: "chat", t: "Préparer l'entretien", d: "Une simulation d'entretien avec un expert de ce type de sélection.", needs: ["entretien"] },
  { icon: "globe", t: "Après l'admission", d: "Test de langue, visa et installation dans le pays.", needs: ["langue", "visa"] },
];

const HOW = [
  { t: "Vous faites votre demande", d: "Votre objectif, ce sur quoi vous voulez de l'aide et les bourses visées." },
  { t: "Un expert vous est attribué", d: "Ancien boursier ou conseiller d'orientation, choisi selon votre langue, votre niveau et vos pays." },
  { t: "Un plan daté", d: "Les étapes sont calées à rebours sur vos dates limites, avec un rappel la veille." },
  { t: "L'expert dépose votre candidature", d: "CV et lettre adaptés, pièces vérifiées, dépôt sur le site officiel avec preuve de dépôt, puis suivi jusqu'au résultat." },
];

function RequestForm({ cm, onDone, initialNeeds = [], onCancel, initialOffer = "standard", scholarshipId }: { cm: CoachingMeta; onDone: () => Promise<void>; initialNeeds?: string[]; onCancel?: () => void; initialOffer?: string; scholarshipId?: number }) {
  const { t } = useT();
  const [apps, setApps] = useState<Application[]>([]);
  const [goal, setGoal] = useState("");
  const [offers, setOffers] = useState<Offer[]>(DEFAULT_OFFERS);
  const [offer, setOffer] = useState(initialOffer === "premium" ? "premium" : "standard");
  useEffect(() => { getOffers().then(setOffers); }, []);
  const maxApps = offer === "premium" ? 3 : 1;
  useEffect(() => { setIds((l) => l.slice(0, offer === "premium" ? 3 : 1)); }, [offer]);
  useEffect(() => {
    if (!scholarshipId) return;
    api<Scholarship>(`/api/scholarships/${scholarshipId}`)
      .then((s) => setGoal((g) => g || `Être accompagné pour candidater à « ${s.title} » (${s.organization}).`))
      .catch(() => {});
  }, [scholarshipId]);
  const [needs, setNeeds] = useState<string[]>(initialNeeds);
  const [ids, setIds] = useState<number[]>([]);
  const [lang, setLang] = useState("fr");
  const [availability, setAvailability] = useState("");
  const [consent, setConsent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api<Application[]>("/api/applications").then(setApps).catch(() => {}); }, []);
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api("/api/accompagnement", {
        method: "POST",
        body: JSON.stringify({ offer, goal, needs, application_ids: ids, preferred_language: lang, availability: availability || null, share_consent: consent }),
      });
      await onDone();
    } catch (e2) { setErr((e2 as Error).message); setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="card mx-auto max-w-3xl space-y-5 p-5 sm:p-8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{t("Accompagnement personnalisé")}</p>
          <h2 className="mt-1 text-xl sm:text-2xl">{t("Demander un accompagnement")}</h2>
        </div>
        {onCancel && <button type="button" className="text-sm text-muted hover:text-ink" onClick={onCancel}>{t("← Retour")}</button>}
      </div>
      <fieldset>
        <legend className="label">{t("Votre formule")}</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {offers.filter((o) => o.code !== "autonome").map((o) => (
            <label key={o.code} className={`flex cursor-pointer flex-col rounded-2xl border p-4 transition ${offer === o.code ? "border-brand bg-brand-soft/40" : "border-line bg-surface hover:border-brand/50"}`}>
              <span className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 font-semibold"><input type="radio" name="offer" value={o.code} checked={offer === o.code} onChange={() => setOffer(o.code)} className="accent-[#3ee0a8]" />{o.name}</span>
                <span className="font-serif text-lg font-semibold">{o.price_label}</span>
              </span>
              <span className="mt-1 text-xs text-muted">{o.description}</span>
            </label>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">{t("Le paiement se règle avec votre conseiller une fois votre demande acceptée. Vous pouvez toujours postuler vous-même gratuitement.")}</p>
      </fieldset>
      <div>
        <label className="label" htmlFor="goal">{t("Votre objectif")}</label>
        <textarea id="goal" className="input" rows={3} required minLength={10} value={goal} onChange={(e) => setGoal(e.target.value)}
          placeholder={t("ex. Obtenir une bourse pour un master en IA en France ou au Canada pour la rentrée prochaine.")} />
      </div>
      <fieldset>
        <legend className="label">{t("Sur quoi voulez-vous de l'aide ?")}</legend>
        <div className="flex flex-wrap gap-2">
          {Object.entries(cm.needs).map(([k, v]) => (
            <button type="button" key={k} onClick={() => setNeeds(toggle(needs, k))} aria-pressed={needs.includes(k)}
              className={`rounded-full border px-3 py-1.5 text-sm ${needs.includes(k) ? "border-brand bg-brand-soft font-semibold text-ink" : "border-line bg-card text-muted hover:border-brand/60"}`}>
              {v}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="label">{t("Bourses concernées ·")} {offer === "premium" ? t("jusqu'à 3") : t("1 bourse")} {t("avec la formule")} {offer === "premium" ? t("Premium") : t("Standard")}</legend>
        {apps.length === 0 ? (
          <p className="text-sm text-muted">{t("Vous n'avez pas encore de bourse dans votre suivi. Votre conseiller vous aidera à les choisir.")}</p>
        ) : (
          <div className="space-y-1">
            {apps.map((a) => (
              <label key={a.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={ids.includes(a.id)} disabled={!ids.includes(a.id) && ids.length >= maxApps} onChange={() => setIds(toggle(ids, a.id))} />
                {a.scholarship.title} <span className="text-muted">· {formatDate(a.scholarship.deadline)}</span>
              </label>
            ))}
            <p className="text-xs text-muted">{t("Si vous n'en cochez aucune, votre conseiller voit tout votre suivi.")}</p>
          </div>
        )}
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="lang">{t("Langue de l'accompagnement")}</label>
          <select id="lang" className="input" value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="fr">{t("Français")}</option>
            <option value="en">{t("Anglais")}</option>
            <option value="ar">{t("Arabe")}</option>
            <option value="pt">{t("Portugais")}</option>
            <option value="es">{t("Espagnol")}</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="dispo">{t("Vos disponibilités")}</label>
          <input id="dispo" className="input" value={availability} onChange={(e) => setAvailability(e.target.value)} placeholder={t("ex. soirs en semaine, samedi matin")} />
        </div>
      </div>
      <label className="flex items-start gap-2 rounded-lg bg-paper p-3 text-sm">
        <input type="checkbox" className="mt-0.5" checked={consent} onChange={(e) => setConsent(e.target.checked)} required />
        <span>{t("J'accepte que mon conseiller voie mon profil, mon CV et mes candidatures pour m'aider. Je peux arrêter l'accompagnement à tout moment.")}</span>
      </label>
      {err && <p className="text-sm text-danger">{err}</p>}
      <button className="btn-primary w-full sm:w-auto" disabled={busy || !consent}>{busy ? "Envoi…" : t("Envoyer ma demande")}</button>
    </form>
  );
}

function Feedback({ c, onDone }: { c: Coaching; onDone: () => void }) {
  const { t } = useT();
  const [rating, setRating] = useState(c.rating ?? 0);
  const [text, setText] = useState(c.feedback ?? "");
  if (c.rating) return <p className="card p-4 text-sm">{t("Merci pour votre avis :")} {"★".repeat(c.rating)}{"☆".repeat(5 - c.rating)}</p>;
  return (
    <div className="card space-y-3 p-5">
      <h3 className="text-lg">{t("Comment s'est passé votre accompagnement ?")}</h3>
      <div className="flex gap-1" role="radiogroup" aria-label={t("Note")}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" role="radio" aria-checked={rating === n} onClick={() => setRating(n)}
            className={`text-2xl ${n <= rating ? "text-warm" : "text-line"}`} aria-label={t("{n} sur 5", { n })}>★</button>
        ))}
      </div>
      <textarea className="input" rows={2} placeholder={t("Un mot pour votre conseiller (facultatif)")} value={text} onChange={(e) => setText(e.target.value)} />
      <button className="btn-primary" disabled={!rating} onClick={async () => {
        await api(`/api/accompagnement/${c.id}/avis`, { method: "POST", body: JSON.stringify({ rating, feedback: text || null }) });
        onDone();
      }}>{t("Envoyer mon avis")}</button>
    </div>
  );
}

function Page() {
  const { t } = useT();
  const [cm, setCm] = useState<CoachingMeta | null>(null);
  const [list, setList] = useState<Coaching[] | null>(null);
  const params = useSearchParams();
  const offreParam = params.get("offre") ?? undefined;
  const bourseParam = Number(params.get("bourse")) || undefined;
  const [asking, setAsking] = useState(Boolean(offreParam && offreParam !== "autonome"));
  const [preset, setPreset] = useState<string[]>(bourseParam ? ["cv", "lettre"] : []);
  useEffect(() => { if (offreParam && offreParam !== "autonome") { setAsking(true); window.scrollTo({ top: 0 }); } }, [offreParam]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () => api<Coaching[]>("/api/accompagnement").then(setList).catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => { getCoachingMeta().then(setCm).catch((e) => setError(e.message)); load(); }, [load]);
  const onChange = useCallback((d: CoachingDetail) => {
    setList((l) => l?.map((x) => (x.id === d.id ? { ...x, status: d.status, rating: d.rating, unread: 0 } : x)) ?? l);
  }, []);

  if (error) return <p className="text-danger">{error}</p>;
  if (!list || !cm) return <p className="text-muted">{t("Chargement…")}</p>;

  const current = list.find((c) => c.status === "demande" || c.status === "en_cours");
  const last = list[0];
  const past = list.filter((c) => c !== current);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-[1.65rem] sm:text-3xl">{t("Accompagnement")}</h1>
        <p className="mt-1 max-w-2xl text-muted">{t("Un expert prépare votre dossier et dépose lui-même votre candidature. Deux formules : Standard pour 1 bourse, Premium pour 3 bourses. Vous pouvez aussi postuler vous-même gratuitement.")}</p>
      </div>

      {current ? (
        <>
          {current.status === "demande" && (
            <div className="card flex flex-wrap items-center justify-between gap-3 border-warm/40 bg-warm-soft p-4 text-sm">
              <p>Votre demande est bien reçue. Un expert va vous être attribué ; vous recevrez une alerte.</p>
              <button className="btn-ghost px-3 py-1 text-xs" onClick={async () => {
                if (!confirm(t("Annuler votre demande d'accompagnement ?"))) return;
                await api(`/api/accompagnement/${current.id}/annuler`, { method: "POST" }); load();
              }}>{t("Annuler la demande")}</button>
            </div>
          )}
          <CoachingWorkspace id={current.id} onChange={onChange} />
          {current.status === "en_cours" && (
            <button className="text-sm text-muted hover:text-danger hover:underline" onClick={async () => {
              if (!confirm(t("Arrêter votre accompagnement ? Votre conseiller sera prévenu."))) return;
              await api(`/api/accompagnement/${current.id}/annuler`, { method: "POST" }); load();
            }}>{t("Arrêter l'accompagnement")}</button>
          )}
        </>
      ) : (
        <>
          {last?.status === "termine" && <Feedback c={last} onDone={load} />}
          {!asking ? (
            <section className="space-y-8">
              <div className="card relative overflow-hidden p-6 sm:p-10">
                <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-mint/15 blur-3xl" />
                <div className="relative grid gap-8 lg:grid-cols-[1fr_1.2fr] lg:items-center">
                  <div>
                    <p className="eyebrow">{t("Conseiller humain · dès 15 000 F CFA")}</p>
                    <h2 className="mt-3 text-[1.65rem] leading-tight sm:text-3xl lg:text-4xl">{t("Un expert dépose votre candidature")} <span className="accent">{t("jusqu'au bout.")}</span></h2>
                    <p className="mt-3 text-sm text-muted">{t("Un ancien boursier ou un conseiller d'orientation, choisi selon votre langue, votre niveau et vos pays. Vous arrêtez quand vous le souhaitez.")}</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {NEEDS_CARDS.map((n) => (
                      <button key={n.t} onClick={() => { setPreset(n.needs); setAsking(true); }}
                        className="group flex gap-3 rounded-2xl border border-line bg-surface p-4 text-left transition hover:border-brand/50">
                        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand"><Icon name={n.icon} className="h-5 w-5" /></span>
                        <span>
                          <span className="flex items-center gap-1 font-semibold">{t(n.t)}<Icon name="arrow" className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" /></span>
                          <span className="mt-0.5 block text-xs text-muted">{t(n.d)}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div>
                <p className="eyebrow">{t("Comment ça se passe")}</p>
                <div className="mt-4 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                  {HOW.map((h, i) => (
                    <div key={h.t}>
                      <div className="grid h-9 w-9 place-items-center rounded-full border border-line bg-card font-mono text-xs text-brand">0{i + 1}</div>
                      <p className="mt-2 font-semibold">{t(h.t)}</p>
                      <p className="mt-1 text-sm text-muted">{t(h.d)}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="eyebrow">{t("Tarifs")}</p>
                <h2 className="mt-2 text-xl sm:text-2xl">{t("Choisissez votre formule")}</h2>
                <div className="mt-5"><Offers scholarshipId={bourseParam} compact /></div>
              </div>
            </section>
          ) : (
            <RequestForm cm={cm} initialNeeds={preset} initialOffer={offreParam} scholarshipId={bourseParam} onCancel={() => setAsking(false)} onDone={async () => { await load(); setAsking(false); }} />
          )}
        </>
      )}

      {past.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-xl">{t("Historique")}</h2>
          <ul className="card divide-y divide-line text-sm">
            {past.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <span className="min-w-0 truncate">{c.goal}</span>
                <span className="text-muted">{cm.statuses[c.status]}{c.offer_name ? ` · ${c.offer_name}${c.price_label ? ` (${c.price_label})` : ""}` : ""}{c.advisor ? ` · ${c.advisor.display_name}` : ""} · {new Date(c.created_at).toLocaleDateString("fr-FR")}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default function AccompagnementPage() {
  return <RequireAuth><Suspense><Page /></Suspense></RequireAuth>;
}
