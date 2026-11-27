// Traduction de l'interface. Le français est la langue source : chaque texte sert de clé
// et sa version anglaise est dans lib/i18n-en.ts. Un texte absent du dictionnaire reste en français.
import EN from "./i18n-en";
import EN_LAUNCH from "./i18n-en-launch";

export type Lang = "fr" | "en";
export const LANG_COOKIE = "sf_lang";
export const LANGS: Lang[] = ["fr", "en"];

type Vars = Record<string, string | number | null | undefined>;

export function translate(lang: Lang, fr: string, vars?: Vars): string {
  let s = lang === "en" ? EN[fr] ?? EN_LAUNCH[fr] ?? fr : fr;
  if (vars) s = s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
  return s;
}

/** Langue de la page, lue dans le navigateur (le serveur l'écrit dans <html lang>). */
export function clientLang(): Lang {
  if (typeof document === "undefined") return "fr";
  return document.documentElement.lang === "en" ? "en" : "fr";
}

export const locale = (lang: Lang) => (lang === "en" ? "en-GB" : "fr-FR");

/** Nom d'un pays dans la langue choisie, à partir de son code ISO. */
export function countryName(code: string, lang: Lang, fallback?: string): string {
  if (lang === "fr" && fallback) return fallback;
  try {
    const n = new Intl.DisplayNames([locale(lang)], { type: "region" }).of(code.toUpperCase());
    if (n && n !== code.toUpperCase()) return n;
  } catch { /* code non ISO */ }
  return fallback ?? code;
}
