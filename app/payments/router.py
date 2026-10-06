from fastapi import APIRouter

from app.authentication.dependencies import AdminUser, CurrentUser
from app.commons.errors import ApiError
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
        raise ApiError(404, "payment_not_found", "Payment not found")
    if not current_user.is_admin and not services.payment_belongs_to_user(
        db, payment, current_user.id
    ):
        raise ApiError(403, "not_payment_owner", "Not your payment")
    return payment

@router.post("/{payment_id}/refund", response_model=PaymentResponse)
def refund_payment(payment_id: int, admin: AdminUser, db: DbSession):
    try:
        return services.refund_payment(db, payment_id)
    except services.PaymentNotFound:
        raise ApiError(404, "payment_not_found", "Payment not found")
    except services.PaymentNotRefundable:
        raise ApiError(409, "payment_not_refundable", "Payment cannot be refunded")