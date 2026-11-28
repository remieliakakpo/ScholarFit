"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { API_URL, Scholarship, api } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Icon from "./Icon";
import { useT } from "./LangProvider";

type Reason = { code: string; label: string };

/** Agenda, partage WhatsApp et signalement d'une erreur, sous la fiche d'une bourse. */
export default function ScholarshipTools({ s }: { s: Scholarship }) {
  const { t } = useT();
  const { me } = useAuth();
  const [url, setUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => setUrl(`${window.location.origin}/bourses/${s.id}`), [s.id]);

  const upcoming = !!s.deadline && new Date(s.deadline) >= new Date(new Date().toDateString());
  const text = `${s.title} (${s.organization})${s.deadline ? ` · ${t("date limite")} ${s.deadline}` : ""}\n${url}`;

  async function share() {
    if (navigator.share) {
      try {
        await navigator.share({ title: s.title, text: `${s.title} (${s.organization})`, url });
        return;
      } catch {
        /* partage annulé : on propose la copie */
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      /* presse-papiers indisponible */
    }
  }

  return (
    <div className="card space-y-2 p-4">
      <a href={`https://wa.me/?text=${encodeURIComponent(text)}`} target="_blank" rel="noopener noreferrer"
        className="btn-ghost w-full justify-start gap-2 text-sm">
        <Icon name="chat" className="h-4 w-4 text-[#25D366]" /> {t("Partager sur WhatsApp")}
      </a>
      <button type="button" onClick={share} className="btn-ghost w-full justify-start gap-2 text-sm">
        <Icon name="share" className="h-4 w-4 text-brand" /> {copied ? t("Lien copié") : t("Partager le lien")}
      </button>
      {upcoming && (
        <a href={`${API_URL}/api/scholarships/${s.id}/calendrier.ics`} download className="btn-ghost w-full justify-start gap-2 text-sm">
          <Icon name="calendar" className="h-4 w-4 text-brand" /> {t("Ajouter la date limite à mon agenda")}
        </a>
      )}
      <button type="button" onClick={() => setOpen(true)} className="w-full pt-1 text-center text-xs text-muted hover:text-warm hover:underline">
        <Icon name="flag" className="mr-1 inline h-3.5 w-3.5" />{t("Signaler une erreur sur cette fiche")}
      </button>
      {open && <ReportDialog s={s} loggedIn={!!me} onClose={() => setOpen(false)} />}
    </div>
  );
}

function ReportDialog({ s, loggedIn, onClose }: { s: Scholarship; loggedIn: boolean; onClose: () => void }) {
  const { t } = useT();
  const [reasons, setReasons] = useState<Reason[]>([]);
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Reason[]>("/api/signalements/motifs").then(setReasons).catch(() => setReasons([]));
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ message: string }>(`/api/scholarships/${s.id}/signalements`, { method: "POST", body: JSON.stringify({ reason, comment: comment || null }) });
      setDone(r.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="report-title" className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <h2 id="report-title" className="text-lg font-semibold">{t("Signaler une erreur")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Fermer")} className="text-muted hover:text-ink"><Icon name="close" /></button>
        </div>
        <p className="mt-1 truncate text-sm text-muted">{s.title}</p>
        {!loggedIn ? (
          <div className="mt-5">
            <p className="text-sm">{t("Connectez-vous pour signaler une erreur : cela nous évite les faux signalements.")}</p>
            <Link href={`/connexion?next=/bourses/${s.id}`} className="btn-primary mt-4 w-full">{t("Se connecter")}</Link>
          </div>
        ) : done ? (
          <div className="mt-5">
            <p className="text-sm text-ok">{done}</p>
            <button type="button" onClick={onClose} className="btn-ghost mt-4 w-full">{t("Fermer")}</button>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-5 space-y-3">
            <fieldset className="space-y-2">
              <legend className="label">{t("Quel est le problème ?")}</legend>
              {reasons.map((r) => (
                <label key={r.code} className="flex items-center gap-2 text-sm">
                  <input type="radio" name="reason" value={r.code} checked={reason === r.code} onChange={() => setReason(r.code)} required />{r.label}
                </label>
              ))}
            </fieldset>
            <div>
              <label className="label" htmlFor="report-comment">{t("Précisions (facultatif)")}</label>
              <textarea id="report-comment" rows={3} maxLength={1000} className="input" value={comment} onChange={(e) => setComment(e.target.value)}
                placeholder={t("Ex. : la date limite indiquée sur le site officiel est le 15 mars.")} />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <button className="btn-primary w-full" disabled={busy || !reason}>{busy ? "…" : t("Envoyer le signalement")}</button>
          </form>
        )}
      </div>
    </div>
  );
}
