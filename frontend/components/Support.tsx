"use client";
import Link from "next/link";
import { useState } from "react";
import Icon from "./Icon";
import { HeartArt } from "./Illustrations";
import { useT } from "@/components/LangProvider";
import { Lang, locale } from "@/lib/i18n";

/*
  Dons pour soutenir l'équipe ScholarFit. Les numéros de réception sont ici :
  modifiez NUMBERS si vous changez de compte Mobile Money.
*/
const NUMBERS = {
  flooz: { label: "Flooz (Moov Money)", number: "+228 98 64 55 43" },
  mixx: { label: "Mixx by Yas", number: "+228 91 12 75 84" },
};
const ALL = [NUMBERS.flooz, NUMBERS.mixx];

type Method = { id: string; name: string; logo?: string; fit?: "contain" | "cover"; numbers: { label: string; number: string }[]; how: string };
const METHODS: Method[] = [
  { id: "flooz", name: "Flooz", logo: "/paiement/flooz.png", fit: "cover", numbers: [NUMBERS.flooz], how: "Depuis votre compte Flooz, faites un transfert vers ce numéro." },
  { id: "mixx", name: "Mixx by Yas", logo: "/paiement/mixx-by-yas.png", fit: "cover", numbers: [NUMBERS.mixx], how: "Depuis votre compte Mixx by Yas, faites un transfert vers ce numéro." },
  { id: "carte", name: "Carte bancaire", numbers: ALL, how: "Depuis l'étranger, payez par carte avec Taptap Send ou LemFi : choisissez le Togo, l'envoi vers Mobile Money, puis l'un de ces numéros." },
  { id: "taptap", name: "Taptap Send", logo: "/paiement/taptap-send.png", fit: "cover", numbers: ALL, how: "Dans Taptap Send, choisissez le Togo puis l'envoi vers Mobile Money (Flooz ou Mixx by Yas), et indiquez l'un de ces numéros." },
  { id: "lemfi", name: "LemFi", logo: "/paiement/lemfi.png", fit: "cover", numbers: ALL, how: "Dans LemFi, choisissez le Togo puis l'envoi vers Mobile Money, et indiquez l'un de ces numéros." },
  { id: "pispi", name: "PI-SPI (BCEAO)", logo: "/paiement/pi-spi.png", fit: "cover", numbers: ALL, how: "Depuis votre banque ou votre portefeuille compatible PI-SPI, envoyez le paiement instantané vers l'un de ces numéros." },
];

const AMOUNTS = [1000, 2500, 5000, 10000];
const fmt = (n: number, lang: Lang) => `${n.toLocaleString(locale(lang))} F CFA`;

export default function Support({ compact = false, asPage = false }: { compact?: boolean; asPage?: boolean }) {
  const { t, lang } = useT();
  const [amount, setAmount] = useState<number | null>(2500);
  const [custom, setCustom] = useState("");
  const [method, setMethod] = useState<Method | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const value = custom ? Number(custom) : amount;

  const copy = async (n: string) => {
    const raw = n.replace(/\s/g, "");
    let ok = false;
    try { await navigator.clipboard.writeText(raw); ok = true; } catch {
      // Navigateurs plus anciens ou page non sécurisée : copie par une zone de texte cachée
      const t = document.createElement("textarea");
      t.value = raw; t.style.position = "fixed"; t.style.opacity = "0";
      document.body.appendChild(t); t.select();
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      t.remove();
    }
    if (ok) { setCopied(n); setTimeout(() => setCopied(null), 2200); }
  };
  const choose = (m: Method) => {
    setMethod(m);
    if (m.numbers.length === 1) copy(m.numbers[0].number); // le numéro est copié tout de suite, prêt à coller
  };

  return (
    <div className={`relative overflow-hidden rounded-3xl border border-line bg-card ${compact ? "p-6 sm:p-8" : "p-6 sm:p-10"}`}>
      <div className="relative grid gap-8 lg:grid-cols-[1fr_1.15fr] lg:items-start">
        <div>
          <p className="eyebrow">{t("Soutenir ScholarFit")}</p>
          {asPage
            ? <h1 className="mt-2 text-[1.65rem] sm:text-3xl lg:text-4xl">{t("Soutenez")} <span className="accent">{t("notre travail.")}</span></h1>
            : <h2 className="mt-2 text-[1.65rem] sm:text-3xl lg:text-4xl">{t("Soutenez")} <span className="accent">{t("notre travail.")}</span></h2>}
          <p className="mt-3 max-w-md text-muted">
            {t("Chaque jour, notre équipe recherche, vérifie et met en ligne des bourses, des stages et des conférences du monde entier, et accompagne les étudiants dans leurs candidatures. Votre don nous permet de continuer et d'ouvrir ces opportunités au plus grand nombre.")}
          </p>
          <ul className="mt-5 space-y-2 text-sm">
            {[t("La recherche et la vérification des offres"), t("L'accompagnement des étudiants qui en ont le plus besoin"), t("L'hébergement et l'amélioration de la plateforme")].map((x) => (
              <li key={x} className="flex gap-2"><Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-brand" />{x}</li>
            ))}
          </ul>
          <HeartArt className="mt-8 hidden w-44 lg:block" />
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5">
          <p className="label">{t("Montant du don")}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {AMOUNTS.map((a) => (
              <button key={a} type="button" onClick={() => { setAmount(a); setCustom(""); }} aria-pressed={!custom && amount === a}
                className={`rounded-xl border px-2 py-2.5 text-sm font-semibold transition ${!custom && amount === a ? "border-brand bg-brand-soft text-brand" : "border-line bg-card text-ink hover:border-brand/50"}`}>
                {a.toLocaleString(locale(lang))} F
              </button>
            ))}
          </div>
          <input className="input mt-2" type="number" min={100} step={100} inputMode="numeric" placeholder={t("Autre montant (F CFA)")} value={custom} onChange={(e) => setCustom(e.target.value)} aria-label={t("Autre montant")} />

          <p className="label mt-5">{t("Choisissez votre moyen de paiement")}</p>
          <div className="grid grid-cols-3 gap-2">
            {METHODS.map((m) => (
              <button key={m.id} type="button" onClick={() => choose(m)} aria-pressed={method?.id === m.id} title={t(m.name)}
                className={`group relative flex h-16 items-center justify-center overflow-hidden rounded-xl border bg-white transition ${method?.id === m.id ? "border-brand ring-2 ring-brand/40" : "border-line hover:border-brand/60"}`}>
                {m.logo
                  ? // eslint-disable-next-line @next/next/no-img-element
                    <img src={m.logo} alt={t(m.name)} className={`h-full w-full ${m.fit === "contain" ? "object-contain p-1" : "object-cover"}`} />
                  : <span className="flex items-center gap-1.5 px-2 text-xs font-semibold text-[#0d1a20]"><Icon name="card" className="h-5 w-5 text-[#0b8a62]" />{t("Carte bancaire")}</span>}
              </button>
            ))}
          </div>

          <div className="mt-4 min-h-[112px]" aria-live="polite">
            {method ? (
              <div key={method.id} className="animate-step-in rounded-xl border border-brand/40 bg-card p-4">
                <p className="text-sm font-semibold">{t(method.name)}{value ? <span className="font-normal text-muted"> · {fmt(value, lang)}</span> : null}</p>
                <p className="mt-1 text-xs text-muted">{t(method.how)}</p>
                <ul className="mt-3 space-y-2">
                  {method.numbers.map((n) => (
                    <li key={n.number} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface px-3 py-2">
                      <span>
                        <span className="block text-[11px] text-muted">{t(n.label)}</span>
                        <span className="font-serif text-lg font-bold tracking-wide">{n.number}</span>
                      </span>
                      <button type="button" onClick={() => copy(n.number)} className={`btn px-3 py-1.5 text-xs ${copied === n.number ? "bg-brand-soft text-brand" : "btn-ghost"}`}>
                        <Icon name={copied === n.number ? "check" : "copy"} className="h-3.5 w-3.5" />{copied === n.number ? t("Numéro copié") : t("Copier")}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">{t("Touchez un moyen de paiement : le numéro s'affiche et se copie automatiquement, prêt à coller dans votre application.")}</p>
            )}
          </div>
          <p className="mt-3 text-xs text-muted">{t("Merci pour votre soutien.")} {compact && <Link href="/soutenir" className="font-semibold text-brand hover:underline">{t("À quoi servent les dons")}</Link>}</p>
        </div>
      </div>
    </div>
  );
}
