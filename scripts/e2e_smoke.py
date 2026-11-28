"""Test de bout en bout de ScholarFit, contre une plateforme qui tourne déjà (site + API).

Passe par le site (relais /api de Next.js), comme un vrai visiteur : catalogue, fiche et son
aperçu, application installable, inscription, sécurité (CSRF, adresse non confirmée), profil,
suivi, agenda, recherches sauvegardées, signalement, export des données, mot de passe,
déconnexion, puis côté administration (signalements, journal, coût de l'IA) et suppression du compte.

    python scripts/e2e_smoke.py                       # site sur http://localhost:3000
    python scripts/e2e_smoke.py --base http://localhost:3100 --admin admin@example.org:admin12345

Crée un compte jetable (e2e-…@example.org) puis le supprime. Sans --admin, la partie
administration est sautée. Code de sortie 1 si une vérification échoue.
"""
from __future__ import annotations

import argparse
import secrets
import sys
import time
from datetime import date

import httpx

RESULTS: list[tuple[bool, str, str]] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((ok, label, detail))
    print(f"  {'OK ' if ok else 'ÉCHEC'}  {label}{f'  ({detail})' if detail and not ok else ''}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:3000", help="adresse du site")
    ap.add_argument("--admin", help="email:motdepasse d'un administrateur (facultatif)")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    started = time.monotonic()

    # Le site envoie cet en-tête sur chaque modification (protection CSRF)
    c = httpx.Client(base_url=base, headers={"X-Requested-With": "ScholarFit"}, timeout=30, follow_redirects=True)
    anon = httpx.Client(base_url=base, timeout=30, follow_redirects=True)

    print(f"ScholarFit, test de bout en bout sur {base}\n")
    print("Public")
    r = c.get("/api/health")
    if not check("API joignable par le site (/api/health)", r.status_code == 200 and r.json().get("ok"), f"{r.status_code}"):
        return report(started)
    items = c.get("/api/scholarships", params={"per_page": 50, "deadline_status": "ouverte,bientot,urgente"}).json()["items"]
    check("Catalogue : des offres ouvertes", len(items) > 0, f"{len(items)}")
    s = next((x for x in items if x.get("deadline")), items[0])
    page = anon.get(f"/bourses/{s['id']}")
    check("Fiche rendue côté serveur", page.status_code == 200 and s["title"][:20] in page.text, f"{page.status_code}")
    check("Aperçu du lien (og:title, og:image)", 'property="og:title"' in page.text and 'property="og:image"' in page.text)
    og = anon.get(f"/bourses/{s['id']}/opengraph-image")
    check("Image d'aperçu générée (PNG)", og.status_code == 200 and og.headers.get("content-type", "").startswith("image/png"), f"{og.status_code}")
    ics = anon.get(f"/api/scholarships/{s['id']}/calendrier.ics")
    check("Date limite en fichier agenda (.ics)", ics.status_code == 200 and "BEGIN:VEVENT" in ics.text, f"{ics.status_code}")
    man = anon.get("/manifest.webmanifest")
    check("Application installable (manifeste)", man.status_code == 200 and man.json().get("short_name") == "ScholarFit", f"{man.status_code}")
    check("Service worker servi (/sw.js)", anon.get("/sw.js").status_code == 200)
    check("En-têtes de sécurité du site", page.headers.get("x-frame-options") == "DENY" and page.headers.get("x-content-type-options") == "nosniff")

    print("\nCompte")
    email = f"e2e-{secrets.token_hex(4)}@example.org"
    pw1, pw2 = f"E2e{secrets.token_hex(5)}", f"E2e{secrets.token_hex(5)}"
    r = c.post("/api/auth/register", json={"email": email, "password": pw1, "accept_terms": True})
    if not check("Inscription", r.status_code == 201, f"{r.status_code} {r.text[:120]}"):
        return report(started)
    set_cookie = r.headers.get("set-cookie", "").lower()
    check("Cookie de session httpOnly, pas de jeton dans la réponse", "httponly" in set_cookie and "access_token" not in r.text)
    check("Sans en-tête X-Requested-With : refusé (CSRF)",
          anon.put("/api/profile", json={"city": "Lomé"}, cookies=c.cookies).status_code == 403)
    me = c.get("/api/auth/me").json()
    check("Adresse pas encore confirmée", me.get("email_verified") is False)
    check("Paiement refusé tant que l'adresse n'est pas confirmée",
          c.post("/api/credits/orders", json={"method": "flooz", "reference": "E2E"}).status_code == 403)
    r = c.put("/api/profile", json={"nationalities": ["TG"], "birth_date": f"{date.today().year - 23}-05-01",
                                     "target_level": "BAC5", "domain": "informatique", "city": "Lomé"})
    check("Profil enregistré", r.status_code == 200 and r.json().get("minimum_ok") is True, f"{r.status_code}")
    check("Bourses classées pour le profil", c.get("/api/matches").status_code == 200)

    print("\nSuivi, agenda, recherches, signalement")
    r = c.post("/api/applications", json={"scholarship_id": s["id"]})
    check("Candidature ajoutée au suivi", r.status_code in (200, 201), f"{r.status_code}")
    cal = c.get("/api/calendrier.ics")
    check("Agenda personnel des dates limites", cal.status_code == 200 and "BEGIN:VCALENDAR" in cal.text, f"{cal.status_code}")
    r = c.post("/api/recherches", json={"name": "E2E Canada", "filters": {"country": "CA", "kind": "bourse"}})
    check("Recherche sauvegardée", r.status_code == 201, f"{r.status_code}")
    ss_id = r.json().get("id") if r.status_code == 201 else None
    check("Liste des recherches", any(x["name"] == "E2E Canada" for x in c.get("/api/recherches").json()))
    r = c.post(f"/api/scholarships/{s['id']}/signalements", json={"reason": "date_fausse", "comment": "Test automatique e2e"})
    check("Signalement d'une fiche", r.status_code == 201, f"{r.status_code}")
    check("Pas de second signalement ouvert sur la même fiche",
          c.post(f"/api/scholarships/{s['id']}/signalements", json={"reason": "autre"}).status_code == 409)
    exp = c.get("/api/profile/export")
    data = exp.json() if exp.status_code == 200 else {}
    check("Export des données (JSON)", exp.status_code == 200 and data.get("account", {}).get("email") == email
          and "password_hash" not in data.get("account", {}) and len(data.get("saved_searches", [])) == 1)
    if ss_id:
        check("Recherche supprimée", c.delete(f"/api/recherches/{ss_id}").status_code == 204)

    print("\nMot de passe et session")
    r = c.post("/api/auth/changer-mot-de-passe", json={"current_password": pw1, "new_password": pw2})
    check("Changement de mot de passe", r.status_code == 200, f"{r.status_code}")
    check("Déconnexion", c.post("/api/auth/logout").status_code == 204)
    check("Plus de session après déconnexion", c.get("/api/auth/me").status_code == 401)
    check("Ancien mot de passe refusé", c.post("/api/auth/login", json={"email": email, "password": pw1}).status_code == 401)
    check("Connexion avec le nouveau mot de passe", c.post("/api/auth/login", json={"email": email, "password": pw2}).status_code == 200)

    if args.admin:
        print("\nAdministration")
        a_email, _, a_pw = args.admin.partition(":")
        a = httpx.Client(base_url=base, headers={"X-Requested-With": "ScholarFit"}, timeout=30)
        if check("Connexion administrateur", a.post("/api/auth/login", json={"email": a_email, "password": a_pw}).status_code == 200):
            reports = a.get("/api/admin/signalements").json()
            mine = [x for x in reports if x.get("comment") == "Test automatique e2e"]
            check("Le signalement apparaît dans l'administration", len(mine) == 1)
            if mine:
                r = a.patch(f"/api/admin/signalements/{mine[0]['id']}", json={"status": "rejete", "note": "Test e2e"})
                check("Signalement traité", r.status_code == 200, f"{r.status_code}")
            log = a.get("/api/admin/audit", params={"action": "signalements"}).json()["items"]
            check("Action inscrite au journal d'audit", any(x["actor"] == a_email for x in log))
            costs = a.get("/api/admin/couts-ia")
            check("Tableau du coût de l'IA", costs.status_code == 200 and "today" in costs.json(), f"{costs.status_code}")
            a.post("/api/auth/logout")
        a.close()

    print("\nNettoyage")
    check("Suppression du compte de test", c.delete("/api/auth/me").status_code == 204)
    c.close()
    anon.close()
    return report(started)


def report(started: float) -> int:
    failed = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} vérifications réussies en {time.monotonic() - started:.1f} s")
    for _, label, detail in failed:
        print(f"  - {label}{f' : {detail}' if detail else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
