import os

from flask import Flask, render_template
from flask_jwt_extended import JWTManager
from config import Config
from models import db
from routes.auth import auth_bp
from routes.ai import ai_bp
from routes.meals import meals_bp

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
jwt = JWTManager(app)
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(ai_bp, url_prefix="/ai")
app.register_blueprint(meals_bp, url_prefix="/meals")

with app.app_context():
    db.create_all()

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/setup")
def setup():
    return render_template("setup.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard_new.html", page="today")

@app.route("/repas")
def meals_page():
    return render_template("meals.html", page="meals")

@app.route("/progression")
def progress_page():
    return render_template("progress.html", page="progress")

@app.route("/coach")
def coach_page():
    return render_template("coach.html", page="coach")

@app.route("/objectifs")
def goals_page():
    return render_template("goals.html", page="goals")

@app.route("/profil")
def profile_page():
    return render_template("profile.html", page="profile")

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
