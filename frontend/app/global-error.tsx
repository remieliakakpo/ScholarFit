"use client";
import { useEffect } from "react";
import { reportError } from "@/lib/report-error";

/** Dernier recours : erreur dans la mise en page elle-même (en-tête, menu). Styles en ligne, car
 *  la feuille de style du site peut ne pas être chargée à ce moment-là. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => reportError(error), [error]);
  return (
    <html lang="fr">
      <body style={{ margin: 0, minHeight: "100vh", display: "grid", placeItems: "center", background: "#0a1016", color: "#eef2f0", fontFamily: "system-ui, sans-serif", padding: 16 }}>
        <div style={{ maxWidth: 420, textAlign: "center" }}>
          <h1 style={{ fontSize: 24 }}>ScholarFit n&apos;a pas pu s&apos;afficher</h1>
          <p style={{ opacity: 0.7, fontSize: 14 }}>L&apos;équipe a été prévenue automatiquement. Réessayez dans un instant.</p>
          <button type="button" onClick={reset} style={{ marginTop: 16, padding: "10px 20px", borderRadius: 999, border: 0, background: "#3ee0a8", color: "#04140e", fontWeight: 600, cursor: "pointer" }}>
            Réessayer
          </button>
        </div>
      </body>
    </html>
  );
}
