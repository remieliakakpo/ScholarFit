"use client";
import { useEffect, useState } from "react";
import { api, getToken } from "./api";

export type Me = { id: number; email: string; name: string; display_name: string; email_verified: boolean; is_admin: boolean; is_advisor: boolean };

/** Compte complété par des valeurs par défaut (un serveur plus ancien n'envoie pas name / display_name / email_verified). */
export function normalizeMe(raw: unknown): Me | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Partial<Me>;
  if (typeof r.email !== "string" || !r.email) return null;
  const name = typeof r.name === "string" ? r.name : "";
  const display = (typeof r.display_name === "string" && r.display_name.trim()) || name.trim() || r.email.split("@")[0];
  return {
    id: Number(r.id) || 0, email: r.email, name, display_name: display,
    // Absent = serveur ancien sans confirmation d'e-mail : on n'affiche pas le bandeau.
    email_verified: r.email_verified !== false,
    is_admin: !!r.is_admin, is_advisor: !!r.is_advisor,
  };
}

/** Tableau de bord de chaque rôle (le même choix que l'API à la connexion). */
export function homeFor(me: Pick<Me, "is_admin" | "is_advisor"> | null): string {
  if (me?.is_admin) return "/admin";
  if (me?.is_advisor) return "/conseiller";
  return "/mes-bourses";
}

/** Prévient toutes les parties de la page que le compte a changé (nom, e-mail confirmé…). */
export function refreshAuth() {
  window.dispatchEvent(new Event("auth-change"));
}

export function useAuth() {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const load = () => {
      if (!getToken()) {
        setMe(null);
        setReady(true);
        return;
      }
      api<unknown>("/api/auth/me")
        .then((m) => setMe(normalizeMe(m)))
        .catch(() => setMe(null))
        .finally(() => setReady(true));
    };
    load();
    window.addEventListener("auth-change", load);
    return () => window.removeEventListener("auth-change", load);
  }, []);

  return { me, ready };
}
