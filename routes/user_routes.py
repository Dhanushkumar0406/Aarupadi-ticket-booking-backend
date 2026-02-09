from flask import Blueprint, jsonify, g

from middleware.auth_middleware import token_required
from models.tour_registration import TourRegistration


user_bp = Blueprint("user", __name__, url_prefix="/api/user")


@user_bp.get("/profile")
@token_required(role="USER")
def profile():
    return jsonify({"user": g.current_user.to_dict()})


@user_bp.get("/ticket")
@token_required(role="USER")
def my_ticket():
    ticket = (
        TourRegistration.query.filter_by(user_id=g.current_user.id)
        .order_by(TourRegistration.created_at.desc())
        .first()
    )
    return jsonify({"ticket": ticket.to_dict() if ticket else None})
