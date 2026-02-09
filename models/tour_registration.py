from datetime import datetime

from models import db


class TourRegistration(db.Model):
    __tablename__ = "tour_registrations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    boarding_point = db.Column(db.String(120), nullable=False)
    temple_name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    is_free = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "boarding_point": self.boarding_point,
            "temple_name": self.temple_name,
            "age": self.age,
            "cost": self.cost,
            "is_free": self.is_free,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
