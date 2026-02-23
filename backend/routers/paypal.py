"""
PayPal Sandbox router — deposits and withdrawals.
"""
import os
import logging
from datetime import datetime

import paypalrestsdk
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()

paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID", ""),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET", ""),
})


class DepositRequest(BaseModel):
    amount: float
    currency: str = "EUR"
    return_url: str = "http://localhost:3000/paypal/success"
    cancel_url: str = "http://localhost:3000/paypal/cancel"


class WithdrawRequest(BaseModel):
    amount: float
    currency: str = "EUR"
    paypal_email: str


@router.post("/deposit")
async def create_deposit(req: DepositRequest):
    """Creates a PayPal order and returns the approval URL."""
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": req.return_url,
            "cancel_url": req.cancel_url,
        },
        "transactions": [{
            "amount": {"total": f"{req.amount:.2f}", "currency": req.currency},
            "description": "AI Trading System — Virtual Wallet Deposit",
        }],
    })

    if payment.create():
        approval_url = next(
            (link.href for link in payment.links if link.rel == "approval_url"), None
        )
        # Log pending transaction
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    """INSERT INTO paypal_transactions (paypal_order_id, type, amount, currency, status)
                    VALUES (:oid, 'DEPOSIT', :amt, :cur, 'PENDING')"""
                ),
                {"oid": payment.id, "amt": req.amount, "cur": req.currency},
            )
        return {"payment_id": payment.id, "approval_url": approval_url}
    else:
        raise HTTPException(status_code=400, detail=str(payment.error))


@router.post("/deposit/execute")
async def execute_deposit(payment_id: str, payer_id: str):
    """Executes an approved PayPal payment and credits virtual wallet."""
    payment = paypalrestsdk.Payment.find(payment_id)
    if payment.execute({"payer_id": payer_id}):
        amount = float(payment.transactions[0].amount.total)
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE virtual_accounts SET balance = balance + :amt, equity = equity + :amt WHERE user_id='default'"),
                {"amt": amount},
            )
            await db.execute(
                text("UPDATE paypal_transactions SET status='COMPLETED', completed_at=NOW() WHERE paypal_order_id=:oid"),
                {"oid": payment_id},
            )
        return {"status": "success", "amount_credited": amount}
    else:
        raise HTTPException(status_code=400, detail=str(payment.error))


@router.post("/withdraw")
async def withdraw(req: WithdrawRequest):
    """Initiates a PayPal payout from virtual wallet."""
    async with AsyncSessionLocal() as db:
        acc = await db.execute(text("SELECT balance FROM virtual_accounts WHERE user_id='default'"))
        row = acc.fetchone()
        if not row or float(row[0]) < req.amount:
            raise HTTPException(status_code=400, detail="Insufficient virtual balance")

        payout = paypalrestsdk.Payout({
            "sender_batch_header": {
                "sender_batch_id": f"payout_{int(datetime.utcnow().timestamp())}",
                "email_subject": "AI Trading — Withdrawal",
            },
            "items": [{
                "recipient_type": "EMAIL",
                "amount": {"value": f"{req.amount:.2f}", "currency": req.currency},
                "receiver": req.paypal_email,
                "note": "Virtual wallet withdrawal",
            }],
        })

        if payout.create(sync_mode=True):
            await db.execute(
                text("UPDATE virtual_accounts SET balance = balance - :amt WHERE user_id='default'"),
                {"amt": req.amount},
            )
            await db.execute(
                text(
                    """INSERT INTO paypal_transactions (paypal_order_id, type, amount, currency, status, completed_at)
                    VALUES (:oid, 'WITHDRAW', :amt, :cur, 'COMPLETED', NOW())"""
                ),
                {"oid": payout.batch_header.payout_batch_id, "amt": req.amount, "cur": req.currency},
            )
            return {"status": "success", "batch_id": payout.batch_header.payout_batch_id}
        else:
            raise HTTPException(status_code=400, detail=str(payout.error))
