from datetime import datetime

from flask import Blueprint, Response, current_app, g, jsonify, request
from sqlalchemy import or_

from middleware.auth_middleware import token_required
from models import db
from models.admin_log import AdminLog
from models.tour_registration import TourRegistration
from models.user import User
from utils.jwt import generate_token
from utils.password import check_password
from utils.pdf_ticket import generate_ticket_pdf


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _get_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _find_admin(identifier):
    if not identifier:
        return None
    return User.query.filter(
        User.role == "ADMIN",
        or_(
            User.email.ilike(identifier),
            User.citizen_id == identifier,
            User.full_name.ilike(identifier),
        ),
    ).first()


def _calculate_cost(age, temple_name):
    prices = current_app.config.get("TEMPLE_PRICES", {})
    threshold = current_app.config.get("FREE_AGE_THRESHOLD", 60)
    price = prices.get(temple_name)
    if price is None:
        return None, False
    if age < threshold:
        return 0, True
    return price, False


@admin_bp.post("/login")
def admin_login():
    data = _get_json()
    identifier = data.get("username") or data.get("email") or data.get("citizen_id")
    password = data.get("password")

    if not identifier or not password:
        return jsonify({"error": "Username and password required."}), 400

    admin = _find_admin(str(identifier).strip())
    if not admin or not check_password(str(password), admin.password):
        return jsonify({"error": "Invalid credentials."}), 401

    if admin.status != "APPROVED":
        return jsonify({"error": "Admin not approved."}), 403

    token = generate_token(
        admin,
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["JWT_EXPIRES_MINUTES"],
    )

    return jsonify(
        {
            "token": token,
            "role": admin.role.lower(),
            "id": admin.id,
            "username": admin.full_name,
        }
    )


@admin_bp.get("/pending-users")
@token_required(role="ADMIN")
def pending_users():
    users = User.query.filter_by(role="USER", status="PENDING").all()
    return jsonify({"users": [user.to_dict() for user in users]})


@admin_bp.post("/approve/<int:user_id>")
@token_required(role="ADMIN")
def approve_user(user_id):
    user = User.query.filter_by(id=user_id, role="USER").first()
    if not user:
        return jsonify({"error": "User not found."}), 404

    user.status = "APPROVED"
    log = AdminLog(admin_id=g.current_user.id, user_id=user.id, action="APPROVED")
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": "User approved", "user": user.to_dict()})


@admin_bp.post("/reject/<int:user_id>")
@token_required(role="ADMIN")
def reject_user(user_id):
    user = User.query.filter_by(id=user_id, role="USER").first()
    if not user:
        return jsonify({"error": "User not found."}), 404

    user.status = "REJECTED"
    log = AdminLog(admin_id=g.current_user.id, user_id=user.id, action="REJECTED")
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": "User rejected", "user": user.to_dict()})


@admin_bp.post("/ticket/<int:user_id>")
@token_required(role="ADMIN")
def issue_ticket(user_id):
    data = _get_json()
    required = ["boarding_point", "temple_name", "age"]
    missing = [field for field in required if data.get(field) in (None, "")]
    if missing:
        return (
            jsonify({"error": "Missing required fields.", "fields": missing}),
            400,
        )

    user = User.query.filter_by(id=user_id, role="USER").first()
    if not user:
        return jsonify({"error": "User not found."}), 404

    if user.status != "APPROVED":
        return jsonify({"error": "User must be approved before issuing a ticket."}), 403

    try:
        age = int(data["age"])
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid age."}), 400

    temple_name = str(data["temple_name"]).strip()
    boarding_point = str(data["boarding_point"]).strip()
    if not temple_name or not boarding_point:
        return jsonify({"error": "Invalid boarding point or temple name."}), 400

    cost, is_free = _calculate_cost(age, temple_name)
    if cost is None:
        return jsonify({"error": "Invalid temple name."}), 400

    ticket = (
        TourRegistration.query.filter_by(user_id=user.id)
        .order_by(TourRegistration.created_at.desc())
        .first()
    )

    if ticket:
        ticket.boarding_point = boarding_point
        ticket.temple_name = temple_name
        ticket.age = age
        ticket.cost = cost
        ticket.is_free = is_free
        ticket.created_at = datetime.utcnow()
    else:
        ticket = TourRegistration(
            user_id=user.id,
            boarding_point=boarding_point,
            temple_name=temple_name,
            age=age,
            cost=cost,
            is_free=is_free,
        )
        db.session.add(ticket)

    db.session.commit()

    return jsonify({
        "message": "Ticket issued",
        "ticket": ticket.to_dict(),
        "pdf_url": f"/api/admin/ticket/{ticket.id}/pdf",
    })


@admin_bp.get("/ticket/<int:ticket_id>/pdf")
@token_required(role="ADMIN")
def download_ticket_pdf(ticket_id):
    ticket = TourRegistration.query.get(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found."}), 404

    user = User.query.get(ticket.user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    pdf_bytes = generate_ticket_pdf(user, ticket)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ticket_MT{ticket.id:05d}.pdf",
        },
    )
