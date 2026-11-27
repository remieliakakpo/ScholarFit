"use client";
import { useEffect, useState } from "react";
import { api, getToken } from "./api";

export type Me = { id: number; email: string; name: string; display_name: string; email_verified: boolean; is_admin: boolean; is_advisor: boolean };

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
      api<Me>("/api/auth/me")
        .then(setMe)
        .catch(() => setMe(null))
        .finally(() => setReady(true));
    };
    load();
    window.addEventListener("auth-change", load);
    return () => window.removeEventListener("auth-change", load);
  }, []);

  return { me, ready };
}
