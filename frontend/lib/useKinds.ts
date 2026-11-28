"use client";
import { useEffect, useState } from "react";
import { getMeta } from "./api";

/** Types d'opportunités affichés (choisis dans l'administration). null tant que ce n'est pas chargé :
 *  on affiche alors tout, pour ne pas faire clignoter les liens. */
export function useEnabledKinds(): string[] | null {
  const [kinds, setKinds] = useState<string[] | null>(null);
  useEffect(() => {
    getMeta().then((m) => setKinds(m.kinds ? Object.keys(m.kinds) : null)).catch(() => setKinds(null));
  }, []);
  return kinds;
}

/** Vrai si le type est affiché (ou si la liste n'est pas encore connue). */
export function kindShown(kinds: string[] | null, kind: string): boolean {
  return kinds === null || kinds.includes(kind);
}
