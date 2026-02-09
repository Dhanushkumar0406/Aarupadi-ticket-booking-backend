from flask import Flask, jsonify
from flask_cors import CORS
import logging
from config.config import SECRET_KEY, DEBUG
from models import init_db
from routes.auth import auth_bp
from routes.citizen import citizen_bp
from routes.registration import registration_bp
from routes.admin import admin_bp
from routes.stats import stats_bp
from routes.audit import audit_bp
from routes.admin_api import admin_api_bp
from routes.user_api import user_api_bp

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["DEBUG"] = DEBUG
app.url_map.strict_slashes = False
CORS(app, resources={r"/*": {"origins": "*"}})

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("werkzeug").setLevel(logging.DEBUG)
logging.getLogger("werkzeug").disabled = False
app.logger.disabled = False
app.logger.setLevel(logging.DEBUG)

# Ensure database and tables exist even when running via `flask run`.
init_db()

@app.route("/")
def home():
    return jsonify({"message": "Free Murugan Temple Tour API v2"})


app.register_blueprint(auth_bp)
app.register_blueprint(citizen_bp)
app.register_blueprint(registration_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(audit_bp)
app.register_blueprint(admin_api_bp)
app.register_blueprint(user_api_bp)


if __name__ == "__main__":
    app.run(debug=DEBUG)
