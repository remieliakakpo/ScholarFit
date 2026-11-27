"use client";
// Dernier filet si l'en-tête ou le menu eux-mêmes plantent : page autonome, sans dépendance au reste du site.
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="fr">
      <body style={{ margin: 0, minHeight: "100vh", display: "grid", placeItems: "center", background: "#0b1119", color: "#e8edf3", fontFamily: "system-ui, sans-serif", padding: 16 }}>
        <div style={{ maxWidth: 420, textAlign: "center" }}>
          <p style={{ fontSize: 20, fontWeight: 600 }}>Un problème est survenu.</p>
          <p style={{ fontSize: 14, opacity: 0.75 }}>Rechargez la page. Si le problème continue, revenez dans quelques minutes : vos données ne sont pas perdues.</p>
          <div style={{ marginTop: 20, display: "flex", gap: 8, justifyContent: "center" }}>
            <button onClick={() => reset()} style={{ padding: "8px 16px", borderRadius: 999, border: 0, background: "#3ee0a8", color: "#04140e", fontWeight: 600, cursor: "pointer" }}>Réessayer</button>
            <a href="/" style={{ padding: "8px 16px", borderRadius: 999, border: "1px solid #2a3442", color: "inherit", textDecoration: "none" }}>Accueil</a>
          </div>
        </div>
      </body>
    </html>
  );
}
