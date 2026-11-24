"use client";
import { useEffect, useState } from "react";
import { api, isSignedIn } from "./api";

export type Me = { id: number; email: string; is_admin: boolean; is_advisor: boolean; email_verified: boolean };

export function useAuth() {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const load = () => {
      if (!isSignedIn()) {
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
