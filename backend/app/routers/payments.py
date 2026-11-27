"""Paiement en ligne (CinetPay ou simulation) : guichet, retour, notifications, suivi et administration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import payments as svc
from ..config import get_settings
from ..db import get_db
from ..i18n import t
from ..models import Payment, User
from ..security import admin_user, current_user

router = APIRouter(prefix="/api/payments", tags=["paiement"])
admin_router = APIRouter(prefix="/api/admin", tags=["administration"])


class CheckoutIn(BaseModel):
    purpose: Literal["abonnement", "accompagnement"]
    coaching_id: int | None = None


class SimulateIn(BaseModel):
    outcome: Literal["paye", "annule"]


def _mine(tx: str, user: User, db: Session) -> Payment:
    p = db.scalars(select(Payment).where(Payment.transaction_id == tx)).first()
    if p is None or (p.user_id != user.id and not user.is_admin):
        raise HTTPException(404, t("Paiement introuvable", "Payment not found"))
    return p


@router.get("/config")
def config():
    return svc.config()


@router.post("/checkout", status_code=201)
def checkout(body: CheckoutIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = svc.create_checkout(user, body.purpose, db, body.coaching_id)
    return svc.out(p)


@router.get("")
def my_payments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ps = db.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.id.desc()).limit(20))
    return [svc.out(p) for p in ps]


@router.get("/{tx}")
def status(tx: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Statut d'un paiement. S'il est en attente, on redemande à CinetPay (page de retour du site)."""
    p = _mine(tx, user, db)
    return svc.out(svc.refresh(p, db))


@router.post("/{tx}/simulate")
def simulate(tx: str, body: SimulateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _mine(tx, user, db)
    if p.user_id != user.id:
        raise HTTPException(403, t("Seul le titulaire peut confirmer ce paiement d'essai.", "Only the account holder can confirm this test payment."))
    return svc.out(svc.simulate(p, body.outcome, db))


# ---------- appels de CinetPay ----------
@router.api_route("/cinetpay/notify", methods=["GET", "POST"], include_in_schema=False)
async def cinetpay_notify(request: Request, db: Session = Depends(get_db)):
    """Notification de CinetPay. GET : test de disponibilité de l'adresse. POST : un paiement a changé."""
    if request.method == "GET":
        return PlainTextResponse("OK")
    form = dict(await request.form())
    if not svc.notify_signature_ok(form, request.headers.get("x-token")):
        return PlainTextResponse("signature", status_code=401)
    tx = str(form.get("cpm_trans_id") or "")
    p = db.scalars(select(Payment).where(Payment.transaction_id == tx)).first() if tx else None
    if p is not None:
        svc.refresh(p, db)  # le statut fait foi seulement s'il vient de l'API CinetPay
    return PlainTextResponse("OK")


@router.api_route("/cinetpay/return", methods=["GET", "POST"], include_in_schema=False)
async def cinetpay_return(request: Request):
    """CinetPay renvoie le candidat ici (souvent en POST) : on le redirige vers la page du site."""
    tx = request.query_params.get("transaction_id") or ""
    if request.method == "POST":
        try:
            form = await request.form()
            tx = str(form.get("transaction_id") or form.get("cpm_trans_id") or tx)
        except Exception:  # noqa: BLE001
            pass
    tx = "".join(ch for ch in tx if ch.isalnum())[:64]
    site = get_settings().site_url.rstrip("/")
    return RedirectResponse(f"{site}/paiement/retour" + (f"?tx={tx}" if tx else ""), status_code=303)


# ---------- administration ----------
@admin_router.get("/payments")
def admin_payments(status: str | None = None, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    stmt = select(Payment).order_by(Payment.id.desc()).limit(300)
    if status:
        stmt = stmt.where(Payment.status == status)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    paid = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paye")
    totals = {
        "month": db.scalar(paid.where(Payment.paid_at >= month_start)) or 0,
        "last_30_days": db.scalar(paid.where(Payment.paid_at >= datetime.now(timezone.utc) - timedelta(days=30))) or 0,
        "all_time": db.scalar(paid) or 0,
        "pending": db.scalar(select(func.count()).select_from(Payment).where(Payment.status == "en_attente")) or 0,
    }
    return {"totals": {**totals, **{f"{k}_label": svc.fcfa(v) for k, v in totals.items() if k != "pending"}},
            "config": svc.config(), "items": [svc.out(p) for p in db.scalars(stmt)]}


@admin_router.post("/payments/{tx}/refresh")
def admin_refresh(tx: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    p = db.scalars(select(Payment).where(Payment.transaction_id == tx)).first()
    if p is None:
        raise HTTPException(404, t("Paiement introuvable", "Payment not found"))
    return svc.out(svc.refresh(p, db))
