"""Paiement en ligne : CinetPay (Mobile Money et cartes dans la zone CFA) ou simulation pour les essais.

Ce qui se paie :
    abonnement     : un mois d'abonnement CV et lettres (SUBSCRIPTION_PRICE). Une fois payé, un
                     CreditOrder « payé » est créé : l'abonnement s'ouvre ou se prolonge exactement
                     comme après une validation manuelle dans /admin.
    accompagnement : l'offre Standard ou Premium d'une demande d'accompagnement (prix figé à la demande).

Déroulé avec CinetPay :
    1. POST /api/payments/checkout crée le paiement et renvoie l'adresse du guichet CinetPay.
    2. Le candidat paie (Flooz, Mixx by Yas, Orange Money, MTN, Wave, carte…).
    3. CinetPay prévient l'API (notify_url) puis renvoie le candidat sur le site (return_url).
    4. Dans les deux cas, l'API redemande le statut à CinetPay (/payment/check) : on ne croit jamais
       une notification sur parole. Le paiement n'est accordé qu'une fois, même si les deux arrivent
       ensemble.
    5. Toutes les heures, le planificateur revérifie les paiements restés en attente.

PAYMENT_PROVIDER=simulation (par défaut) : un faux guichet sur le site permet d'essayer tout le
parcours sans argent. PAYMENT_PROVIDER=manuel : pas de paiement en ligne, seulement l'envoi sur les
numéros puis la validation dans /admin.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import i18n
from .config import get_settings
from .i18n import t
from .mailer import email_button, send_email
from .models import Coaching, CreditOrder, Payment, User

log = logging.getLogger("paiements")

STATUSES = {"en_attente": "En attente", "paye": "Payé", "echoue": "Échoué", "annule": "Annulé"}
STATUSES_EN = {"en_attente": "Pending", "paye": "Paid", "echoue": "Failed", "annule": "Cancelled"}
PENDING_GIVE_UP = timedelta(days=2)
# Champs de la notification CinetPay, dans l'ordre utilisé pour la signature x-token
NOTIFY_FIELDS = ("cpm_site_id", "cpm_trans_id", "cpm_trans_date", "cpm_amount", "cpm_currency", "signature",
                 "payment_method", "cel_phone_num", "cpm_phone_prefixe", "cpm_language", "cpm_version",
                 "cpm_payment_config", "cpm_page_action", "cpm_custom", "cpm_designation", "cpm_error_message")


class ProviderError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: datetime | None) -> datetime | None:
    if d is not None and d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def fcfa(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " F CFA"


def provider() -> str:
    s = get_settings()
    p = s.payment_provider.strip().lower()
    p = p if p in ("cinetpay", "simulation", "manuel") else "simulation"
    if p == "simulation" and s.is_production:
        # Le faux guichet n'existe jamais en ligne : sans CinetPay, paiement par transfert validé dans /admin.
        return "manuel"
    return p


def online_enabled() -> bool:
    return provider() in ("cinetpay", "simulation")


def config() -> dict:
    p = provider()
    return {
        "online": online_enabled(),
        "provider": p,
        "test_mode": p == "simulation",
        "label": t("Payer par Mobile Money ou carte", "Pay by Mobile Money or card"),
        "methods": ["Flooz", "Mixx by Yas", "Orange Money", "MTN MoMo", "Wave", "Visa", "Mastercard"],
        "note": t("Paiement sécurisé par CinetPay. Votre accès est activé dès la confirmation du paiement.",
                  "Secure payment by CinetPay. Your access is activated as soon as the payment is confirmed."),
    }


# ------------------------------------------------------------------ CinetPay
def _cinetpay_ready() -> None:
    s = get_settings()
    if not (s.cinetpay_apikey and s.cinetpay_site_id):
        raise HTTPException(503, t("Le paiement en ligne n'est pas encore configuré. Utilisez le paiement par transfert.",
                                   "Online payment is not configured yet. Please use the transfer option."))


def _split_name(full: str | None, email: str) -> tuple[str, str]:
    parts = (full or "").strip().split()
    if len(parts) >= 2:
        return parts[-1], " ".join(parts[:-1])
    if parts:
        return parts[0], parts[0]
    base = email.split("@")[0]
    return base, base


def cinetpay_init(p: Payment, user: User) -> str:
    s = get_settings()
    prof = user.profile
    surname, name = _split_name(prof.full_name if prof else None, user.email)
    phone = "".join(ch for ch in (prof.phone or "") if ch.isdigit() or ch == "+") if prof else ""
    payload = {
        "apikey": s.cinetpay_apikey,
        "site_id": s.cinetpay_site_id,
        "transaction_id": p.transaction_id,
        "amount": p.amount,
        "currency": p.currency,
        "description": p.description[:200] or "ScholarFit",
        "notify_url": s.api_public_url.rstrip("/") + "/api/payments/cinetpay/notify",
        "return_url": s.api_public_url.rstrip("/") + "/api/payments/cinetpay/return",
        "channels": "ALL",
        "lang": "en" if i18n.is_en() else "fr",
        "metadata": f"user:{user.id}",
        # Champs demandés par CinetPay pour le paiement par carte
        "customer_id": str(user.id),
        "customer_name": name[:50],
        "customer_surname": surname[:50],
        "customer_email": user.email,
        "customer_phone_number": phone or "",
        "customer_address": ((prof.address or prof.city) if prof else None) or "Lomé",
        "customer_city": (prof.city if prof else None) or "Lomé",
        "customer_country": (prof.residence_country if prof else None) or "TG",
        "customer_state": (prof.residence_country if prof else None) or "TG",
        "customer_zip_code": "00000",
    }
    try:
        r = httpx.post(s.cinetpay_api_url.rstrip("/") + "/payment", json=payload, timeout=30)
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ProviderError(str(e)) from e
    url = (data.get("data") or {}).get("payment_url")
    if str(data.get("code")) != "201" or not url:
        raise ProviderError(f"{data.get('code')} {data.get('message')} {data.get('description', '')}".strip())
    return url


def cinetpay_check(transaction_id: str) -> dict:
    """Statut auprès de CinetPay : {"status": paye|echoue|en_attente, "method", "ref", "message", "amount"}."""
    s = get_settings()
    payload = {"apikey": s.cinetpay_apikey, "site_id": s.cinetpay_site_id, "transaction_id": transaction_id}
    try:
        r = httpx.post(s.cinetpay_api_url.rstrip("/") + "/payment/check", json=payload, timeout=30)
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ProviderError(str(e)) from e
    d = data.get("data") or {}
    raw = str(d.get("status") or "").upper()
    code = str(data.get("code"))
    if code == "00" and raw == "ACCEPTED":
        status = "paye"
    elif raw in ("REFUSED", "CANCELED", "CANCELLED") or code in ("600", "602", "627"):
        status = "echoue"
    else:  # WAITING_FOR_CUSTOMER, 662, 623…
        status = "en_attente"
    amount = d.get("amount")
    try:
        amount = int(float(amount)) if amount is not None else None
    except (TypeError, ValueError):
        amount = None
    return {"status": status, "method": d.get("payment_method"), "ref": d.get("operator_id"),
            "message": str(data.get("message") or "")[:300], "amount": amount, "currency": d.get("currency")}


def notify_signature_ok(form: dict, token: str | None) -> bool:
    """Vérifie l'en-tête x-token des notifications (si CINETPAY_SECRET_KEY est renseignée)."""
    secret = get_settings().cinetpay_secret_key
    if not secret:
        return True  # de toute façon on revérifie le statut auprès de CinetPay
    if not token:
        return False
    data = "".join(str(form.get(k, "")) for k in NOTIFY_FIELDS)
    expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, token)


# ------------------------------------------------------------------ création
def _new_tx() -> str:
    return "SF" + _now().strftime("%y%m%d") + secrets.token_hex(6).upper()


def create_checkout(user: User, purpose: str, db: Session, coaching_id: int | None = None) -> Payment:
    if not online_enabled():
        raise HTTPException(409, t("Le paiement en ligne est désactivé. Utilisez le paiement par transfert.",
                                   "Online payment is turned off. Please use the transfer option."))
    s = get_settings()
    coaching = None
    if purpose == "abonnement":
        amount = s.subscription_price
        desc = t("Abonnement ScholarFit CV et lettres, 1 mois", "ScholarFit CV and letters subscription, 1 month")
    elif purpose == "accompagnement":
        coaching = db.get(Coaching, coaching_id) if coaching_id else None
        if coaching is None or coaching.student_id != user.id:
            raise HTTPException(404, t("Accompagnement introuvable", "Support request not found"))
        if (coaching.payment_status or "a_payer") != "a_payer" or not coaching.price:
            raise HTTPException(409, t("Cet accompagnement est déjà réglé.", "This support request is already paid."))
        amount = coaching.price
        offer = "Premium" if coaching.offer == "premium" else "Standard"
        desc = t(f"Accompagnement {offer} ScholarFit", f"ScholarFit {offer} support")
    else:
        raise HTTPException(422, t("Paiement inconnu", "Unknown payment"))
    if amount <= 0 or amount % 5:
        raise HTTPException(422, t("Montant invalide", "Invalid amount"))

    prov = provider()
    p = Payment(transaction_id=_new_tx(), user_id=user.id, purpose=purpose, coaching_id=coaching.id if coaching else None,
                amount=amount, currency="XOF", description=desc, provider=prov, status="en_attente")
    db.add(p)
    db.flush()
    if prov == "simulation":
        p.checkout_url = s.site_url.rstrip("/") + f"/paiement/simulation?tx={p.transaction_id}"
    else:
        _cinetpay_ready()
        try:
            p.checkout_url = cinetpay_init(p, user)
        except ProviderError as e:
            log.warning("CinetPay a refusé l'initialisation %s : %s", p.transaction_id, e)
            p.status = "echoue"
            p.provider_message = str(e)[:300]
            db.commit()
            raise HTTPException(502, t("Le service de paiement ne répond pas pour le moment. Réessayez dans quelques minutes ou utilisez le paiement par transfert.",
                                       "The payment service is not responding right now. Please try again in a few minutes or use the transfer option.")) from e
    db.commit()
    return p


# ------------------------------------------------------------------ confirmation
def _fulfil(p: Payment, db: Session) -> None:
    """Accorde ce qui a été payé. Appelé une seule fois par paiement (voir mark_paid)."""
    if p.purpose == "abonnement":
        order = CreditOrder(user_id=p.user_id, amount=p.amount, currency=p.currency, method=p.provider,
                            reference=p.transaction_id, status="paye", paid_at=p.paid_at)
        db.add(order)
        db.flush()
        p.credit_order_id = order.id
    elif p.purpose == "accompagnement" and p.coaching_id:
        c = db.get(Coaching, p.coaching_id)
        if c is not None:
            c.payment_status = "paye"
            from .coaching import notify

            offer = "Premium" if c.offer == "premium" else "Standard"
            if c.advisor is not None:
                notify(db, c.advisor.user, f"acc-{c.id}-paye", f"Le candidat a réglé l'offre {offer} : le dossier est prêt à être traité.")
            for admin in db.scalars(select(User).where(User.is_admin.is_(True))):
                notify(db, admin, f"acc-{c.id}-paye", f"Paiement reçu pour l'accompagnement {offer} n° {c.id} ({fcfa(p.amount)}).")


def _receipt(p: Payment, db: Session) -> None:
    user = db.get(User, p.user_id)
    if user is None:
        return
    token = i18n.set_lang(user.lang or "fr")
    try:
        what = p.description
        if p.purpose == "abonnement":
            nxt = t("Votre abonnement est actif : vous pouvez préparer vos CV et lettres adaptés dès maintenant.",
                    "Your subscription is active: you can prepare your tailored CVs and letters right away.")
            button = email_button(t("Préparer mes documents", "Prepare my documents"), "/cv")
        else:
            nxt = t("Votre expert prend en charge votre dossier. Vous retrouvez son plan et vos échanges dans votre espace d'accompagnement.",
                    "Your expert is now handling your application. You will find the plan and your messages in your support space.")
            button = email_button(t("Ouvrir mon accompagnement", "Open my support space"), "/accompagnement")
        send_email(db, user.email, t("Paiement confirmé", "Payment confirmed"),
                   t(f"Bonjour,\n\nNous avons bien reçu votre paiement de {fcfa(p.amount)} pour : {what}.\n\nRéférence : {p.transaction_id}\n\n{nxt}",
                     f"Hello,\n\nWe have received your payment of {fcfa(p.amount)} for: {what}.\n\nReference: {p.transaction_id}\n\n{nxt}"),
                   button=button, kind="paiement", key=f"paiement-{p.transaction_id}")
    finally:
        i18n._lang.reset(token)


def mark_paid(p: Payment, db: Session, method: str | None = None, ref: str | None = None) -> bool:
    """Passe le paiement en « payé » et accorde l'accès, une seule fois (mise à jour conditionnelle)."""
    now = _now()
    res = db.execute(update(Payment).where(Payment.id == p.id, Payment.status != "paye")
                     .values(status="paye", paid_at=now, checked_at=now, method=method or p.method, provider_ref=ref or p.provider_ref))
    if res.rowcount != 1:
        db.rollback()
        db.refresh(p)
        return False
    db.refresh(p)
    _fulfil(p, db)
    db.commit()
    _receipt(p, db)
    db.commit()
    log.info("Paiement %s confirmé (%s, %s F)", p.transaction_id, p.purpose, p.amount)
    return True


def refresh(p: Payment, db: Session) -> Payment:
    """Redemande le statut d'un paiement en attente à CinetPay."""
    if p.status != "en_attente" or p.provider != "cinetpay":
        return p
    try:
        st = cinetpay_check(p.transaction_id)
    except ProviderError as e:
        log.info("Vérification CinetPay impossible pour %s : %s", p.transaction_id, e)
        return p
    p.checked_at = _now()
    p.provider_message = st["message"]
    if st["status"] == "paye":
        if st["amount"] is not None and st["amount"] < p.amount:
            log.warning("Montant payé insuffisant pour %s : %s au lieu de %s", p.transaction_id, st["amount"], p.amount)
            p.status = "echoue"
            p.provider_message = t("Montant reçu inférieur au prix", "Amount received lower than the price")
            db.commit()
            return p
        mark_paid(p, db, method=st["method"], ref=st["ref"])
    elif st["status"] == "echoue":
        p.status = "echoue"
        p.method = st["method"] or p.method
        db.commit()
    else:
        if _now() - (_aware(p.created_at) or _now()) > PENDING_GIVE_UP:
            p.status = "annule"
        db.commit()
    return p


def simulate(p: Payment, outcome: str, db: Session) -> Payment:
    if p.provider != "simulation":
        raise HTTPException(409, t("Ce paiement n'est pas un paiement d'essai.", "This is not a test payment."))
    if p.status != "en_attente":
        return p
    if outcome == "paye":
        mark_paid(p, db, method="SIMULATION", ref="TEST-" + p.transaction_id[-6:])
    else:
        p.status = "annule"
        p.checked_at = _now()
        db.commit()
    return p


def reconcile(db: Session) -> dict[str, int]:
    """Planificateur : revérifie les paiements CinetPay en attente depuis plus de 5 minutes."""
    since = _now() - timedelta(minutes=5)
    counts = {"verifies": 0, "payes": 0}
    for p in db.scalars(select(Payment).where(Payment.status == "en_attente", Payment.provider == "cinetpay")):
        if (_aware(p.created_at) or _now()) > since:
            continue
        counts["verifies"] += 1
        if refresh(p, db).status == "paye":
            counts["payes"] += 1
    # paiements d'essai abandonnés
    old = _now() - PENDING_GIVE_UP
    for p in db.scalars(select(Payment).where(Payment.status == "en_attente", Payment.provider == "simulation")):
        if (_aware(p.created_at) or _now()) < old:
            p.status = "annule"
    db.commit()
    return counts


def out(p: Payment) -> dict:
    labels = i18n.loc(STATUSES, STATUSES_EN)
    return {
        "transaction_id": p.transaction_id, "purpose": p.purpose, "coaching_id": p.coaching_id,
        "amount": p.amount, "currency": p.currency, "amount_label": fcfa(p.amount), "description": p.description,
        "provider": p.provider, "status": p.status, "status_label": labels.get(p.status, p.status),
        "method": p.method, "checkout_url": p.checkout_url if p.status == "en_attente" else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        "email": p.user.email if p.user else None,
    }
