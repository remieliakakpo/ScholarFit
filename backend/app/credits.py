"""Dossiers CV + lettre : le premier est offert, ensuite abonnement mensuel à 2 500 F CFA.

Un dossier correspond à une bourse : il couvre la version adaptée du CV et la lettre de
motivation pour cette bourse, avec quelques relances de génération. Chaque compte reçoit
DOC_FREE_PACKS dossier(s) offert(s). Ensuite, l'abonnement (SUBSCRIPTION_PRICE F CFA pour
SUBSCRIPTION_DAYS jours) permet de préparer jusqu'à SUBSCRIPTION_MONTHLY_PACKS dossiers sur la
période. Le diagnostic du CV, la modification manuelle des textes et les téléchargements restent
gratuits et illimités, comme la candidature elle-même sur le site officiel.

Paiement : Mobile Money (Flooz, Mixx by Yas), transfert (TapTap Send, LemFi) ou PI-SPI de la
BCEAO vers les numéros de ScholarFit. L'étudiant déclare son paiement avec la référence de la
transaction ; un administrateur le valide dans /admin et l'abonnement démarre (ou est prolongé
d'un mois s'il est encore actif).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .i18n import is_en, t
from .models import CreditOrder, DocPack, User

ORDER_STATUSES = {"en_verification": "En vérification", "paye": "Payé", "refuse": "Refusé"}


def payment_methods() -> list[dict]:
    s = get_settings()
    return [
        {"code": "flooz", "label": "Flooz", "logo": "/paiement/flooz.png", "number": s.payment_flooz_number,
         "how": t("Depuis votre compte Flooz (Moov Africa), envoyez le montant au numéro ci-dessous.", "From your Flooz (Moov Africa) account, send the amount to the number below.")},
        {"code": "mixx", "label": "Mixx by Yas", "logo": "/paiement/mixx-by-yas.png", "number": s.payment_mixx_number,
         "how": t("Depuis votre compte Mixx by Yas, envoyez le montant au numéro ci-dessous.", "From your Mixx by Yas account, send the amount to the number below.")},
        {"code": "taptap_send", "label": "TapTap Send", "logo": "/paiement/taptap-send.png", "number": s.payment_flooz_number,
         "how": t("Depuis l'étranger, choisissez le Togo puis un envoi Mobile Money vers le numéro ci-dessous.", "From abroad, choose Togo and then a Mobile Money transfer to the number below.")},
        {"code": "lemfi", "label": "LemFi", "logo": "/paiement/lemfi.png", "number": s.payment_mixx_number,
         "how": t("Depuis l'étranger, choisissez le Togo puis un envoi Mobile Money vers le numéro ci-dessous.", "From abroad, choose Togo and then a Mobile Money transfer to the number below.")},
        {"code": "pi_spi", "label": "PI-SPI (BCEAO)", "logo": "/paiement/pi-spi.png", "number": s.payment_flooz_number,
         "how": t("Depuis votre application bancaire ou Mobile Money compatible PI-SPI, payez vers le numéro ci-dessous.", "From a banking or Mobile Money app that supports PI-SPI, pay to the number below.")},
    ]


def _aware(d: datetime | None) -> datetime | None:
    if d is not None and d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _fcfa(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " F CFA"


def _date_label(d: datetime) -> str:
    return d.strftime("%d/%m/%Y") if not is_en() else d.strftime("%d %b %Y")


def subscription_periods(user: User, db: Session) -> list[tuple[datetime, datetime]]:
    """Périodes d'abonnement payées, dans l'ordre. Un paiement validé pendant un abonnement actif
    prolonge l'abonnement à partir de sa fin (le mois payé n'est jamais perdu)."""
    days = get_settings().subscription_days
    orders = db.scalars(select(CreditOrder).where(CreditOrder.user_id == user.id, CreditOrder.status == "paye")).all()
    starts = sorted(_aware(o.paid_at) or _aware(o.created_at) or datetime.now(timezone.utc) for o in orders)
    out: list[tuple[datetime, datetime]] = []
    end: datetime | None = None
    for paid in starts:
        start = max(paid, end) if end else paid
        end = start + timedelta(days=days)
        out.append((start, end))
    return out


def current_period(user: User, db: Session, now: datetime | None = None) -> tuple[datetime, datetime] | None:
    now = now or datetime.now(timezone.utc)
    return next(((a, b) for a, b in subscription_periods(user, db) if a <= now < b), None)


def _packs(user: User, db: Session, source: str, since: datetime | None = None) -> int:
    dates = db.scalars(select(DocPack.created_at).where(DocPack.user_id == user.id, DocPack.source == source)).all()
    if since is None:
        return len(dates)
    return sum(1 for c in dates if (_aware(c) or since) >= since)


def _state(user: User, db: Session) -> dict:
    s = get_settings()
    free_left = max(0, s.doc_free_packs - _packs(user, db, "offert"))
    period = current_period(user, db)
    used_month = _packs(user, db, "abonnement", since=period[0]) if period else 0
    month_left = max(0, s.subscription_monthly_packs - used_month) if period else 0
    periods = subscription_periods(user, db)
    until = periods[-1][1] if period and periods else None
    return {"free_left": free_left, "period": period, "used_month": used_month, "month_left": month_left, "until": until}


def summary(user: User, db: Session) -> dict:
    s = get_settings()
    st = _state(user, db)
    pending = db.scalar(select(func.count()).select_from(CreditOrder).where(CreditOrder.user_id == user.id, CreditOrder.status == "en_verification")) or 0
    packs = db.scalars(select(DocPack).where(DocPack.user_id == user.id).order_by(DocPack.created_at.desc())).all()
    paid_months = db.scalar(select(func.count()).select_from(CreditOrder).where(CreditOrder.user_id == user.id, CreditOrder.status == "paye")) or 0
    return {
        "free_total": s.doc_free_packs,
        "free_left": st["free_left"],
        "paid_total": paid_months,
        "used": len(packs),
        "available": st["free_left"] + st["month_left"],
        "pending_orders": pending,
        "price": s.subscription_price,
        "price_label": _fcfa(s.subscription_price) + t(" par mois", " per month"),
        "regenerations": s.doc_pack_regenerations,
        "subscription": {
            "active": st["period"] is not None,
            "until": st["until"].isoformat() if st["until"] else None,
            "until_label": _date_label(st["until"]) if st["until"] else None,
            "monthly_packs": s.subscription_monthly_packs,
            "used_this_period": st["used_month"],
            "left_this_period": st["month_left"],
            "days": s.subscription_days,
        },
        "packs": [
            {"scholarship_id": pk.scholarship_id, "scholarship_title": pk.scholarship.title if pk.scholarship else None,
             "cv_runs": pk.cv_runs, "letter_runs": pk.letter_runs, "source": pk.source}
            for pk in packs
        ],
        "methods": payment_methods(),
    }


def find_pack(user: User, scholarship_id: int | None, db: Session) -> DocPack | None:
    stmt = select(DocPack).where(DocPack.user_id == user.id)
    stmt = stmt.where(DocPack.scholarship_id.is_(None)) if scholarship_id is None else stmt.where(DocPack.scholarship_id == scholarship_id)
    return db.scalars(stmt).first()


def use_pack(user: User, scholarship_id: int | None, kind: str, db: Session) -> DocPack:
    """Ouvre (ou reprend) le dossier de cette bourse et compte une génération ``kind`` (cv | lettre).

    Lève 402 (``abonnement_requis`` ou ``limite_mensuelle``) si aucun dossier n'est disponible,
    429 si les relances du dossier sont épuisées.
    """
    s = get_settings()
    pack = find_pack(user, scholarship_id, db)
    if pack is None:
        st = _state(user, db)
        if st["free_left"] > 0:
            source = "offert"
        elif st["month_left"] > 0:
            source = "abonnement"
        elif st["period"] is not None:
            renew = _date_label(st["period"][1])
            raise HTTPException(402, {
                "code": "limite_mensuelle",
                "message": t(f"Vous avez préparé les {s.subscription_monthly_packs} dossiers compris dans votre abonnement pour cette période. De nouveaux dossiers seront disponibles le {renew}. Vous pouvez encore modifier et télécharger vos documents.",
                             f"You have prepared the {s.subscription_monthly_packs} application packs included in your subscription for this period. New packs will be available on {renew}. You can still edit and download your documents."),
                "price": s.subscription_price,
            })
        else:
            raise HTTPException(402, {
                "code": "abonnement_requis",
                "message": t(f"Votre dossier offert a déjà été utilisé. L'abonnement à {_fcfa(s.subscription_price)} par mois vous permet de préparer jusqu'à {s.subscription_monthly_packs} dossiers par mois, avec un CV et une lettre adaptés à chaque bourse.",
                             f"Your free application pack has been used. The {_fcfa(s.subscription_price)} monthly subscription lets you prepare up to {s.subscription_monthly_packs} packs a month, each with a CV and letter tailored to the scholarship."),
                "price": s.subscription_price,
            })
        pack = DocPack(user_id=user.id, scholarship_id=scholarship_id, source=source)
        db.add(pack)
        db.flush()
    runs = pack.cv_runs if kind == "cv" else pack.letter_runs
    if runs >= s.doc_pack_regenerations:
        what = t("du CV", "CV") if kind == "cv" else t("de la lettre", "letter")
        raise HTTPException(429, {
            "code": "relances_epuisees",
            "message": t(f"Vous avez utilisé les {s.doc_pack_regenerations} générations {what} prévues pour cette bourse. Vous pouvez encore modifier le texte et le télécharger.",
                         f"You have used the {s.doc_pack_regenerations} {what} generations included for this scholarship. You can still edit the text and download it."),
        })
    return pack


def count_run(pack: DocPack, kind: str) -> None:
    if kind == "cv":
        pack.cv_runs += 1
    else:
        pack.letter_runs += 1


def create_order(user: User, method: str, reference: str | None, payer_phone: str | None, db: Session) -> CreditOrder:
    if method not in {m["code"] for m in payment_methods()}:
        raise HTTPException(422, t("Moyen de paiement inconnu", "Unknown payment method"))
    order = CreditOrder(user_id=user.id, amount=get_settings().subscription_price, currency="XOF", method=method,
                        reference=(reference or "").strip()[:120] or None, payer_phone=(payer_phone or "").strip()[:50] or None)
    db.add(order)
    db.commit()
    return order


def set_order_status(order: CreditOrder, status: str, db: Session) -> CreditOrder:
    if status not in ORDER_STATUSES:
        raise HTTPException(422, t("Statut inconnu", "Unknown status"))
    order.status = status
    order.paid_at = datetime.now(timezone.utc) if status == "paye" else None
    db.commit()
    return order
