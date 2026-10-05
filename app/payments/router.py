from fastapi import APIRouter, HTTPException

from app.authentication.dependencies import AdminUser, CurrentUser
from app.database import DbSession

from . import services
from .schemas import PaymentResponse

router = APIRouter(prefix="/payments", tags=["payments"])

@router.get("/me", response_model=list[PaymentResponse])
def read_my_payments(current_user: CurrentUser, db: DbSession):
    return services.get_user_payments(db, current_user.id)

@router.get("", response_model=list[PaymentResponse])
def read_all_payments(admin: AdminUser, db: DbSession):
    return services.get_all_payments(db)

@router.get("/{payment_id}", response_model=PaymentResponse)
def read_payment(payment_id: int, current_user: CurrentUser, db: DbSession):
    payment = services.get_payment(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not current_user.is_admin and not services.payment_belongs_to_user(
        db, payment, current_user.id
    ):
        raise HTTPException(status_code=403, detail="Not your payment")
    return payment

@router.post("/{payment_id}/refund", response_model=PaymentResponse)
def refund_payment(payment_id: int, admin: AdminUser, db: DbSession):
    try:
        return services.refund_payment(db, payment_id)
    except services.PaymentNotFound:
        raise HTTPException(status_code=404, detail="Payment not found")
    except services.PaymentNotRefundable:
        raise HTTPException(status_code=409, detail="Payment cannot be refunded")