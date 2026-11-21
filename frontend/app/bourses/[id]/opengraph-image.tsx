// Image d'aperçu quand on partage une fiche (WhatsApp, Facebook, LinkedIn…), générée à la demande.
import { ImageResponse } from "next/og";

export const alt = "ScholarFit";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";

type S = { title: string; organization: string; deadline: string | null; full_funding: boolean; kind?: string; study_countries?: string[] };

function frDate(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

export default async function Image({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let s: S | null = null;
  try {
    const r = await fetch(`${API}/api/scholarships/${encodeURIComponent(id)}`, { next: { revalidate: 3600 } });
    if (r.ok) s = await r.json();
  } catch {
    s = null;
  }
  const title = s?.title ?? "Bourses d'études, stages et conférences";
  const kind = s?.kind === "stage" ? "Stage" : s?.kind === "conference" ? "Conférence" : "Bourse";
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 64, background: "#0b0c1d", color: "#f4f5ff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", width: 44, height: 44, borderRadius: 12, background: "#3ee0a8" }} />
          <div style={{ fontSize: 34, fontWeight: 700 }}>ScholarFit</div>
          {s && <div style={{ marginLeft: 24, fontSize: 24, color: "#0b0c1d", background: "#ffc979", padding: "6px 18px", borderRadius: 999 }}>{kind}</div>}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ fontSize: title.length > 70 ? 52 : 64, fontWeight: 700, lineHeight: 1.1 }}>{title.length > 110 ? title.slice(0, 107) + "…" : title}</div>
          {s && <div style={{ fontSize: 30, color: "#a9acd0" }}>{s.organization}</div>}
        </div>
        <div style={{ display: "flex", gap: 20, fontSize: 28 }}>
          {s?.deadline && <div style={{ display: "flex", background: "#1b1d3a", padding: "12px 24px", borderRadius: 16 }}>Date limite : {frDate(s.deadline)}</div>}
          {s?.full_funding && <div style={{ display: "flex", background: "#123d33", color: "#3ee0a8", padding: "12px 24px", borderRadius: 16 }}>Financement complet</div>}
          {!s && <div style={{ display: "flex", color: "#3ee0a8" }}>Les offres auxquelles vous avez droit, classées pour vous</div>}
        </div>
      </div>
    ),
    size,
  );
}
