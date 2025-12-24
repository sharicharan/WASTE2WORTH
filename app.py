from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, base64
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ================= CONFIG =================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///waste.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

db = SQLAlchemy(app)

# ================= MODEL =================
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # 👤 USER IDENTIFIER (for per-user tracking)
    user_id = db.Column(db.String(100))

    waste_type = db.Column(db.String(100))
    latitude = db.Column(db.String(50))
    longitude = db.Column(db.String(50))

    before_image = db.Column(db.String(200))
    after_image = db.Column(db.String(200))

    status = db.Column(db.String(50), default="Pending")

    # ⭐ FEEDBACK FEATURE
    feedback = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ================= CREATE DB =================
with app.app_context():
    db.create_all()

# ================= HOME (CITIZEN PAGE) =================
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# ================= SUBMIT REPORT =================
@app.route("/submit", methods=["POST"])
def submit():
    waste_type = request.form["waste_type"]
    latitude = request.form["latitude"]
    longitude = request.form["longitude"]

    # 👤 USER ID FROM FRONTEND (localStorage)
    user_id = request.form.get("user_id")

    image_file = None

    # CAMERA IMAGE (base64)
    captured_image = request.form.get("captured_image")
    if captured_image:
        image_data = captured_image.split(",")[1]
        image_bytes = base64.b64decode(image_data)
        filename = f"{int(datetime.utcnow().timestamp())}.jpg"
        with open(os.path.join(app.config["UPLOAD_FOLDER"], filename), "wb") as f:
            f.write(image_bytes)
        image_file = filename

    # FILE UPLOAD
    elif "before_image" in request.files:
        file = request.files["before_image"]
        if file and file.filename != "":
            filename = secure_filename(
                f"{int(datetime.utcnow().timestamp())}_{file.filename}"
            )
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_file = filename

    report = Report(
        user_id=user_id,
        waste_type=waste_type,
        latitude=latitude,
        longitude=longitude,
        before_image=image_file,
        status="Pending"
    )

    db.session.add(report)
    db.session.commit()

    # 🔁 Redirect with user id so only this user's reports are shown
    return redirect(url_for("status", user=user_id))

# ================= STATUS PAGE (USER-SPECIFIC) =================
@app.route("/status")
def status():
    user_id = request.args.get("user")

    if user_id:
        reports = (
            Report.query
            .filter_by(user_id=user_id)
            .order_by(Report.created_at.desc())
            .all()
        )
    else:
        reports = []

    return render_template("status.html", reports=reports)

# ================= FEEDBACK (ONLY AFTER COMPLETION) =================
@app.route("/feedback/<int:report_id>", methods=["POST"])
def feedback(report_id):
    report = db.session.get(Report, report_id)

    if report and report.status == "Completed":
        report.feedback = request.form["feedback"]
        db.session.commit()

    return redirect(url_for("status", user=report.user_id))

# ================= WORKER PANEL =================
@app.route("/worker", methods=["GET"])
def worker():
    reports = Report.query.order_by(Report.created_at.desc()).all()
    return render_template("worker.html", reports=reports)

# ================= WORKER COMPLETE =================
@app.route("/worker/complete/<int:report_id>", methods=["POST"])
def worker_complete(report_id):
    report = db.session.get(Report, report_id)

    file = request.files.get("after_image")
    if file and file.filename != "":
        filename = secure_filename(
            f"after_{report_id}_{file.filename}"
        )
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        report.after_image = filename
        report.status = "Completed"
        db.session.commit()

    return redirect(url_for("worker"))

# ================= ADMIN PANEL =================
@app.route("/admin")
def admin():
    total = Report.query.count()
    completed = Report.query.filter_by(status="Completed").count()
    pending = Report.query.filter_by(status="Pending").count()
    percent = int((completed / total) * 100) if total else 0

    reports = Report.query.order_by(Report.created_at.desc()).all()

    return render_template(
        "admin.html",
        total=total,
        completed=completed,
        pending=pending,
        percent=percent,
        reports=reports
    )

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
