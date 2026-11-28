"use client";
import { useRef, useState } from "react";
import Icon from "@/components/Icon";
import { useT } from "@/components/LangProvider";
import { ApiError, API_URL, CoachingDetail, CoachingFile, api, getToken } from "@/lib/api";

const CATEGORY: Record<CoachingFile["category"], string> = {
  livrable: "Document livré par l'expert",
  preuve_depot: "Preuve de dépôt",
  piece: "Pièce du candidat",
};

function size(n: number) {
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} Mo` : `${Math.max(1, Math.round(n / 1024))} Ko`;
}

/** Documents de l'accompagnement : pièces envoyées par le candidat, livrables et preuve de dépôt de l'expert. */
export default function CoachingFiles({ c, open, isAdvisor, reload }: { c: CoachingDetail; open: boolean; isAdvisor: boolean; reload: () => void }) {
  const { t, lang } = useT();
  const input = useRef<HTMLInputElement>(null);
  const [category, setCategory] = useState<CoachingFile["category"]>(isAdvisor ? "livrable" : "piece");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const files = c.files ?? [];

  async function upload(f: File) {
    setBusy(true);
    setError(null);
    const fd = new FormData();
    fd.append("file", f);
    fd.append("category", category);
    fd.append("note", note);
    try {
      await api(`/api/accompagnement/${c.id}/fichiers`, { method: "POST", body: fd });
      setNote("");
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function download(f: CoachingFile) {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/accompagnement/${c.id}/fichiers/${f.id}`, { headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
      if (!res.ok) throw new ApiError(res.status, t("Téléchargement impossible"));
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = f.filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove(f: CoachingFile) {
    if (!confirm(t("Supprimer ce document ?"))) return;
    await api(`/api/accompagnement/${c.id}/fichiers/${f.id}`, { method: "DELETE" }).catch((e) => setError(e.message));
    reload();
  }

  return (
    <div className="space-y-4">
      {open && (
        <div className="card p-4 sm:p-5">
          <p className="font-semibold">{isAdvisor ? t("Livrer un document au candidat") : t("Envoyer une pièce à votre expert")}</p>
          <p className="mt-1 text-sm text-muted">{t("PDF, Word, JPG ou PNG, 8 Mo au plus.")}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-[auto_1fr_auto] sm:items-end">
            {isAdvisor && (
              <div>
                <label className="label" htmlFor="file-cat">{t("Type")}</label>
                <select id="file-cat" className="input" value={category} onChange={(e) => setCategory(e.target.value as CoachingFile["category"])}>
                  <option value="livrable">{t("Document livré par l'expert")}</option>
                  <option value="preuve_depot">{t("Preuve de dépôt")}</option>
                </select>
              </div>
            )}
            <div className={isAdvisor ? "" : "sm:col-span-2"}>
              <label className="label" htmlFor="file-note">{t("Note (facultatif)")}</label>
              <input id="file-note" className="input" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)}
                placeholder={isAdvisor ? t("Ex. CV revu pour la bourse Eiffel") : t("Ex. Relevés de notes de licence")} />
            </div>
            <div>
              <input ref={input} type="file" className="sr-only" id="file-up" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
              <label htmlFor="file-up" className={`btn-primary w-full cursor-pointer ${busy ? "pointer-events-none opacity-60" : ""}`}>
                <Icon name="upload" className="h-4 w-4" /> {busy ? t("Envoi…") : t("Choisir un fichier")}
              </label>
            </div>
          </div>
          {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        </div>
      )}
      {files.length === 0 ? (
        <p className="card p-8 text-center text-sm text-muted">
          {isAdvisor ? t("Aucun document pour l'instant. Les documents que vous livrez apparaissent ici pour le candidat.") : t("Aucun document pour l'instant. Les documents préparés par votre expert apparaîtront ici.")}
        </p>
      ) : (
        <ul className="card divide-y divide-line">
          {files.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${f.category === "piece" ? "bg-surface text-muted" : "bg-brand-soft text-brand"}`}>
                <Icon name={f.category === "preuve_depot" ? "check" : "file"} className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{f.filename}</p>
                <p className="text-xs text-muted">
                  {t(CATEGORY[f.category])} · {size(f.size)} · {new Date(f.created_at).toLocaleDateString(lang === "en" ? "en-GB" : "fr-FR")}
                  {f.note ? ` · ${f.note}` : ""}
                </p>
              </div>
              <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => download(f)}>{t("Télécharger")}</button>
              {f.mine && open && <button className="text-xs text-muted hover:text-danger" onClick={() => remove(f)}>{t("Supprimer")}</button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
