from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from datetime import datetime

# Initialize the Flask app
app = Flask(__name__)

# Configure the database connection.
# The 'os.environ.get()' method gets the DATABASE_URL environment variable set on Render.
# The fallback is for local development with a SQLite database.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///alfurqan.db')
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database and migrations
db = SQLAlchemy(app)
migrate = Migrate(app, db) # This line is crucial for the 'flask db' command

# ---------------------------
# MODELS
# ---------------------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    reg_number = db.Column(db.String(50), unique=True, nullable=False)
    student_class = db.Column(db.String(50), nullable=False)
    payments = db.relationship("Payment", backref="student", lazy=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_type = db.Column(db.String(100))
    term = db.Column(db.String(20))
    session = db.Column(db.String(20))
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)


# ---------------------------
# AUTH (Simple Admin Login)
# ---------------------------
ADMIN_USER = "admin"
ADMIN_PASS = "password"  # 🔴 change in production

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "error")
    return render_template("index.html")


@app.route('/dashboard')
def dashboard():
    if not session.get("admin"):
        return redirect(url_for("index"))

    total_students = Student.query.count()
    total_payments = db.session.query(db.func.sum(Payment.amount_paid)).scalar() or 0
    outstanding_balance = 0
    recent_payments = Payment.query.order_by(Payment.payment_date.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        total_students=total_students,
        total_payments=total_payments,
        outstanding_balance=outstanding_balance,
        recent_payments=recent_payments
    )


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


# ---------------------------
# STUDENTS & PAYMENTS
# ---------------------------
@app.route("/add-student", methods=["GET", "POST"])
def add_student():
    if not session.get("admin"):
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form["name"]
        reg_number = request.form["reg_number"]
        student_class = request.form["student_class"]
        student = Student(name=name, reg_number=reg_number, student_class=student_class)
        db.session.add(student)
        db.session.commit()
        flash("Student added successfully!", "success")
        return redirect(url_for("add_student"))
    return render_template("add_student.html")


@app.route("/student/<int:student_id>/payments")
def student_payments(student_id):
    if not session.get("admin"):
        return redirect(url_for("index"))

    student = Student.query.get_or_404(student_id)
    payments = Payment.query.filter_by(student_id=student_id).all()
    return render_template("student_payments.html", student=student, payments=payments)


@app.route("/add-payment", methods=["GET", "POST"])
def add_payment():
    if not session.get("admin"):
        return redirect(url_for("index"))

    if request.method == "POST":
        student_id = request.form["student_id"]
        
        # Safe way to handle the amount_paid field
        amount_paid_str = request.form.get("amount_paid")
        if not amount_paid_str:
            flash("Amount paid is required.", "error")
            return redirect(url_for("add_payment"))
        
        try:
            amount_paid = float(amount_paid_str)
        except ValueError:
            flash("Invalid amount. Please enter a valid number.", "error")
            return redirect(url_for("add_payment"))
            
        payment_type = request.form["payment_type"]
        term = request.form["term"]
        session_year = request.form["session"]

        payment = Payment(
            amount_paid=amount_paid,
            payment_date=datetime.today(),
            payment_type=payment_type,
            term=term,
            session=session_year,
            student_id=student_id
        )
        db.session.add(payment)
        db.session.commit()
        flash("Payment recorded successfully!", "success")
        return redirect(url_for("add_payment"))

    return render_template("add_payment.html")


@app.route("/search-students")
def search_students():
    if not session.get("admin"):
        return redirect(url_for("index"))

    query = request.args.get("q", "")
    results = []
    if query:
        results = Student.query.filter(
            (Student.name.ilike(f"%{query}%")) |
            (Student.reg_number.ilike(f"%{query}%"))
        ).all()
    return {
        "students": [
            {"id": s.id, "name": s.name, "reg_number": s.reg_number}
            for s in results
        ]
    }


# ---------------------------
# RECEIPT GENERATOR
# ---------------------------
@app.route("/receipt-generator", methods=["GET", "POST"])
def receipt_generator():
    if not session.get("admin"):
        return redirect(url_for("index"))

    search_results = []
    if request.method == "POST":
        query = request.form.get("search_query")
        if query:
            search_results = Student.query.filter(
                (Student.name.ilike(f"%{query}%")) |
                (Student.reg_number.ilike(f"%{query}%"))
            ).all()
    return render_template("receipt_generator.html", search_results=search_results)


@app.route("/view-receipt/<int:payment_id>")
def view_receipt(payment_id):
    if not session.get("admin"):
        return redirect(url_for("index"))

    payment = Payment.query.get_or_404(payment_id)
    student = payment.student

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Logo
    if os.path.exists("alfurqan_logo.jpg"):
        p.drawImage("alfurqan_logo.jpg", 50, height - 120, width=80, height=60)

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, height - 50, "ALFURQAN ACADEMY")
    p.setFont("Helvetica", 10)
    p.drawString(200, height - 65, "Mai’adua | Motto: Academic Excellence")
    p.drawString(200, height - 80, "Tel: 07067702084, 08025076989")

    # Receipt Title
    p.setFont("Helvetica-Bold", 14)
    p.drawString(230, height - 140, "PAYMENT RECEIPT")

    # Student Info
    y = height - 180
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Student Name: {student.name}")
    p.drawString(50, y - 20, f"Reg Number: {student.reg_number}")
    p.drawString(50, y - 40, f"Class: {student.student_class}")

    # Payment Info
    p.drawString(50, y - 80, f"Date: {payment.payment_date.strftime('%Y-%m-%d')}")
    p.drawString(50, y - 100, f"Amount Paid: ₦{payment.amount_paid:,.2f}")
    p.drawString(50, y - 120, f"Payment Type: {payment.payment_type}")
    p.drawString(50, y - 140, f"Term: {payment.term}")
    p.drawString(50, y - 160, f"Session: {payment.session}")
    p.drawString(50, y - 180, f"Receipt No: {payment.id}")

    # Footer
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(200, 80, "Thank you for your payment!")

    # Signatures
    p.setFont("Helvetica", 12)
    p.drawString(50, 120, "______________________")
    p.drawString(50, 105, "Admin")

    p.drawString(350, 120, "______________________")
    p.drawString(350, 105, "Bursar")

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        download_name=f"receipt_{payment.id}.pdf"
    )


# ---------------------------
# INIT
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
