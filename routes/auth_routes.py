from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import or_

from models import db
from models.user import User
from utils.jwt import generate_token
from utils.password import hash_password


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _get_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _find_user(identifier):
    if not identifier:
        return None
    return User.query.filter(
        or_(
            User.email.ilike(identifier),
            User.citizen_id == identifier,
            User.full_name.ilike(identifier),
        )
    ).first()


@auth_bp.post("/register")
def register():
    data = _get_json()
    required = ["full_name", "email", "citizen_id"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return (
            jsonify({"error": "Missing required fields.", "fields": missing}),
            400,
        )

    full_name = str(data["full_name"]).strip()
    email = str(data["email"]).strip().lower()
    citizen_id = str(data["citizen_id"]).strip()

    if not full_name or not email or not citizen_id:
        return jsonify({"error": "All fields are required."}), 400

    exists = User.query.filter(
        or_(User.email == email, User.citizen_id == citizen_id)
    ).first()
    if exists:
        if exists.role != "USER":
            return jsonify({"error": "Email or Citizen ID already exists."}), 409
        if exists.status == "PENDING":
            return (
                jsonify(
                    {
                        "message": "Registration already submitted. Please wait for admin approval.",
                        "user": exists.to_dict(),
                    }
                ),
                200,
            )
        if exists.status == "REJECTED":
            exists.full_name = full_name
            exists.email = email
            exists.citizen_id = citizen_id
            exists.status = "PENDING"
            db.session.commit()
            return (
                jsonify(
                    {
                        "message": "Registration resubmitted. Please wait for admin approval.",
                        "user": exists.to_dict(),
                    }
                ),
                200,
            )
        return jsonify({"error": "Account already approved. Please login."}), 409

    user = User(
        full_name=full_name,
        email=email,
        password=hash_password(f"{citizen_id}:{email}"),
        citizen_id=citizen_id,
        role="USER",
        status="PENDING",
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Registered", "user": user.to_dict()}), 201


@auth_bp.post("/login")
def login():
    data = _get_json()
    identifier = data.get("email") or data.get("citizen_id") or data.get("username")

    if not identifier:
        return jsonify({"error": "Email or Citizen ID required."}), 400

    user = _find_user(str(identifier).strip())
    if not user:
        return jsonify({"error": "Invalid credentials."}), 401

    if user.role != "USER":
        return jsonify({"error": "User login only."}), 403

    if user.status == "REJECTED":
        return jsonify({"error": "Account has been rejected."}), 403
    if user.status != "APPROVED":
        return jsonify({"error": "Account pending approval."}), 403

    token = generate_token(
        user,
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["JWT_EXPIRES_MINUTES"],
    )

    return jsonify(
        {
            "token": token,
            "role": user.role.lower(),
            "id": user.id,
            "username": user.full_name,
        }
    )


@auth_bp.post("/logout")
def logout():
    return jsonify({"message": "Logged out"})
