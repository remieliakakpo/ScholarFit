"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, signOut } from "@/lib/api";
import { Me, homeFor, useAuth } from "@/lib/useAuth";
import { kindShown, useEnabledKinds } from "@/lib/useKinds";
import VerifyEmailBanner from "./VerifyEmailBanner";
import AuthModal from "./AuthModal";
import Footer from "./Footer";
import Icon, { Logo } from "./Icon";
import LangToggle from "./LangToggle";
import { useT } from "./LangProvider";
import ThemeToggle from "./ThemeToggle";

const APP_LINKS = [
  { href: "/mes-bourses", label: "Mes bourses", icon: "star" },
  { href: "/bourses", label: "Explorer", icon: "search" },
  { href: "/suivi", label: "Suivi", icon: "kanban" },
  { href: "/accompagnement", label: "Accompagnement", icon: "people" },
  { href: "/cv", label: "Mon CV", icon: "file" },
  { href: "/profil", label: "Profil", icon: "user" },
];

const TITLES: [string, string][] = [
  ["/mes-bourses", "Mes bourses"],
  ["/bourses", "Explorer les bourses"],
  ["/suivi", "Suivi"],
  ["/accompagnement", "Accompagnement"],
  ["/cv", "Mon CV"],
  ["/lettre", "Lettre de motivation"],
  ["/preparer", "Préparer ma candidature"],
  ["/profil", "Profil"],
  ["/conseiller", "Espace conseiller"],
  ["/admin", "Administration"],
];

const PUBLIC_PATHS = ["/", "/connexion", "/questionnaire", "/soutenir", "/verifier-email", "/mot-de-passe-oublie", "/reinitialiser", "/confidentialite", "/conditions", "/a-propos", "/desabonner", "/hors-ligne", "/tarifs"];
const PUBLIC_PREFIXES = ["/destinations"];

function PublicShell({ children, me }: { children: React.ReactNode; me: Me | null }) {
  const loggedIn = !!me;
  const [open, setOpen] = useState(false);
  const kinds = useEnabledKinds();
  const path = usePathname();
  const { t } = useT();
  const links = [
    { href: "/bourses", label: t("Bourses") },
    ...(kindShown(kinds, "stage") ? [{ href: "/bourses?kind=stage", label: t("Stages") }] : []),
    { href: "/questionnaire", label: t("Mon profil en 5 étapes") },
    { href: "/#comment", label: t("Comment ça marche") },
    { href: "/tarifs", label: t("Tarifs") },
  ];
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line/60 bg-paper/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
          <Link href="/" aria-label="ScholarFit"><Logo className="h-6 sm:h-7" /></Link>
          <div className="flex items-center gap-2 xl:hidden"><LangToggle /><ThemeToggle /><button className="rounded-full border border-line p-2 text-ink" onClick={() => setOpen(!open)} aria-label="Menu" aria-expanded={open}>
            <Icon name={open ? "close" : "menu"} />
          </button></div>
          <nav className={`${open ? "flex" : "hidden"} absolute left-0 right-0 top-full flex-col gap-1 border-b border-line bg-paper px-4 py-4 shadow-lg xl:static xl:flex xl:flex-row xl:items-center xl:gap-1 xl:border-0 xl:bg-transparent xl:p-0 xl:shadow-none`}>
            {links.map((l) => (
              <Link key={l.href} href={l.href} onClick={() => setOpen(false)}
                className={`whitespace-nowrap rounded-full px-3 py-2 text-sm ${path === l.href ? "text-ink" : "text-muted hover:text-ink"}`}>{l.label}</Link>
            ))}
            <LangToggle className="hidden xl:flex xl:ml-2" /><ThemeToggle className="hidden xl:grid" />
            {me ? (
              <>
                <span className="whitespace-nowrap px-3 py-2 text-sm text-muted xl:ml-2">{t("Salut, {name}", { name: me.display_name })}</span>
                <Link href={homeFor(me)} className="btn-primary whitespace-nowrap xl:ml-1" onClick={() => setOpen(false)}>{t("Mon espace")}</Link>
              </>
            ) : (
              <>
                <Link href="/connexion" onClick={() => setOpen(false)} className="whitespace-nowrap rounded-full px-3 py-2 text-sm text-muted hover:text-ink">{t("Connexion")}</Link>
                <Link href="/connexion?mode=inscription" className="btn-primary xl:ml-1" onClick={() => setOpen(false)}>{t("Commencer")}</Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main>{path === "/" ? children : <div className="mx-auto max-w-6xl px-4 pb-20 pt-8 sm:px-6">{children}</div>}</main>
      <Footer loggedIn={loggedIn} />
    </div>
  );
}

function AppShell({ children, me }: { children: React.ReactNode; me: Me | null }) {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { t } = useT();
  useEffect(() => setOpen(false), [path]);

  const extra = [
    ...(me?.is_advisor ? [{ href: "/conseiller", label: t("Espace conseiller"), icon: "chat" }] : []),
    ...(me?.is_admin ? [{ href: "/admin", label: "Admin", icon: "settings" }] : []),
  ];
  const title = t(TITLES.find(([p]) => path.startsWith(p))?.[1] ?? "ScholarFit");
  const item = (l: { href: string; label: string; icon: string }) => {
    const active = path.startsWith(l.href);
    return (
      <Link key={l.href} href={l.href}
        className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${active ? "bg-brand-soft font-semibold text-brand" : "text-muted hover:bg-paper hover:text-ink"}`}>
        <Icon name={l.icon} className={`h-[18px] w-[18px] ${active ? "text-brand" : ""}`} />
        {t(l.label)}
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-paper">
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-card px-3 py-4 transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <Link href="/" className="px-2 pb-5"><Logo /></Link>
        <nav className="space-y-0.5">{APP_LINKS.map(item)}</nav>
        {extra.length > 0 && <nav className="mt-4 space-y-0.5 border-t border-line pt-4">{extra.map(item)}</nav>}
        <div className="mt-auto space-y-3">
          {!path.startsWith("/accompagnement") && !me?.is_advisor && !me?.is_admin && (
            <Link href="/accompagnement" className="block rounded-2xl border border-line bg-[linear-gradient(135deg,color-mix(in_srgb,var(--color-mint)_16%,transparent),color-mix(in_srgb,var(--color-gold)_12%,transparent))] p-4 transition hover:border-brand/50">
              <span className="eyebrow">{t("Dès 15 000 F CFA")}</span>
              <p className="mt-1 font-serif text-[15px] font-semibold leading-snug">{t("Faites relire votre dossier par un expert.")}</p>
              <span className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand">{t("Demander")} <Icon name="arrow" className="h-3.5 w-3.5" /></span>
            </Link>
          )}
          <button onClick={async () => { await signOut(); router.push("/"); }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted hover:bg-paper hover:text-ink">
            <Icon name="logout" className="h-[18px] w-[18px]" /> {t("Déconnexion")}
          </button>
        </div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line bg-card/90 px-4 py-3 backdrop-blur sm:px-8">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <button className="shrink-0 rounded-lg border border-line p-1.5 lg:hidden" onClick={() => setOpen(true)} aria-label="Menu"><Icon name="menu" /></button>
            <span className="truncate font-serif text-base font-bold tracking-tight text-ink sm:text-lg">{title}</span>
          </div>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <LangToggle />
          <ThemeToggle />
          {me && (
            <Link href="/profil" className="flex items-center gap-2 text-sm text-muted hover:text-ink" title={me.email}>
              <span className="hidden max-w-[240px] truncate sm:inline">{t("Salut,")} <span className="font-semibold text-ink">{me.display_name}</span></span>
              <span className="grid h-8 w-8 place-items-center rounded-full bg-mint text-xs font-bold uppercase text-[#04140e]">{(me.display_name || me.email)[0]}</span>
            </Link>
          )}
          </div>
        </header>
        {me && !me.email_verified && <VerifyEmailBanner email={me.email} />}
        <main className="mx-auto max-w-6xl px-4 pb-20 pt-6 sm:px-8">{children}</main>
        <Footer loggedIn />
      </div>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const { me, ready } = useAuth();
  const path = usePathname();
  const isPublic = PUBLIC_PATHS.includes(path) || PUBLIC_PREFIXES.some((p) => path.startsWith(p)) || (ready && !me);
  return (
    <>
      {isPublic ? <PublicShell me={me}>{children}</PublicShell> : <AppShell me={me}>{children}</AppShell>}
      {!me && <AuthModal />}
    </>
  );
}
