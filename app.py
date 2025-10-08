from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from datetime import datetime
from sqlalchemy import UniqueConstraint, func
from sqlalchemy.orm import joinedload

# ---------------------------
# APP INITIALIZATION
# ---------------------------
app = Flask(__name__)

# ---------------------------
# DATABASE CONFIG
# ---------------------------
db_url = os.environ.get("DATABASE_URL", "sqlite:///alfurqan.db")

# Convert Render's postgres:// → postgresql+pg8000://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ---------------------------
# DB + MIGRATIONS
# ---------------------------
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ---------------------------
# MODELS
# ---------------------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    reg_number = db.Column(db.String(50), unique=True, nullable=False)
    student_class = db.Column(db.String(50), nullable=False)
    # school_id has been removed, assuming the DB constraint is also dropped.
    payments = db.relationship("Payment", backref="student", lazy="select")

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_type = db.Column(db.String(100))
    term = db.Column(db.String(20))
    session = db.Column(db.String(20))
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)

class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_class = db.Column(db.String(50), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    session = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    __table_args__ = (UniqueConstraint('student_class', 'term', 'session', name='_class_term_session_uc'),)

# ---------------------------
# AUTH (Simple Admin Login)
# ---------------------------
ADMIN_USER = "admin"
ADMIN_PASS = "password"  # 🔴 Change this in production!


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


# ---------------------------
# DASHBOARD ENHANCEMENT
# ---------------------------
@app.route('/dashboard')
def dashboard():
    if not session.get("admin"):
        return redirect(url_for("index"))

    total_students = Student.query.count()
    total_payments = db.session.query(db.func.sum(Payment.amount_paid)).scalar() or 0
    
    # ENHANCEMENT: Calculate Outstanding Balance
    # 1. Calculate Total Fees due across all recorded Fee records
    total_fees_due = db.session.query(db.func.sum(Fee.amount)).scalar() or 0
    
    # 2. Calculate Outstanding Balance (Total Fees Due - Total Paid)
    outstanding_balance = total_fees_due - total_payments
    
    recent_payments = Payment.query.order_by(Payment.payment_date.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        total_students=total_students,
        total_payments=total_payments,
        # Ensure outstanding balance is not negative
        outstanding_balance=max(0, outstanding_balance),
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
        
        # FIX: school_id logic removed entirely
        student = Student(name=name, reg_number=reg_number, student_class=student_class)
        
        try:
            db.session.add(student)
            db.session.commit()
            flash("Student added successfully!", "success")
            return redirect(url_for("add_student"))
        except Exception as e:
            db.session.rollback()
            # Catch UniqueConstraint error specifically (e.g., duplicate reg_number)
            if 'unique constraint' in str(e).lower():
                flash("Error: Registration number already exists.", "error")
            else:
                # Log or display other errors
                flash(f"Error adding student: {e}", "error")
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
        student_id = request.form.get("student_id")
        
        # --- FIX: Capture the outstanding balance directly from the form ---
        outstanding_balance_str = request.form.get("outstanding_balance_input")
        # --- END FIX ---
        
        amount_paid_str = request.form.get("amount_paid")
        payment_type = request.form.get("payment_type")
        term = request.form.get("term")
        session_year = request.form.get("session")

        if not student_id:
            flash("Please search for and select a student from the list.", "error")
            return redirect(url_for("add_payment"))
        
        try:
            amount_paid = float(amount_paid_str)
            # Convert user input to float for the receipt display
            remaining_balance_on_receipt = float(outstanding_balance_str)
        except (ValueError, TypeError):
            flash("Invalid amount or outstanding balance format.", "error")
            return redirect(url_for("add_payment"))

        student = Student.query.get(student_id)
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("add_payment"))

        # *** The complex calculation logic is REMOVED ***

        payment = Payment(
            amount_paid=amount_paid,
            payment_date=datetime.today().date(),
            payment_type=payment_type,
            term=term,
            session=session_year,
            student_id=student_id
        )
        db.session.add(payment)
        db.session.commit()
        
        # Pass the user's input directly as the remaining balance for the receipt
        session['remaining_balance'] = remaining_balance_on_receipt 
        
        flash("Payment recorded successfully! Generating receipt...", "success")
        return redirect(url_for("view_receipt", payment_id=payment.id))

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
            {"id": s.id, "name": s.name, "reg_number": s.reg_number, "student_class": s.student_class}
            for s in results
        ]
    }

@app.route("/student-financials")
def student_financials():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 403

    student_id = request.args.get("student_id")
    term = request.args.get("term")
    session_year = request.args.get("session")

    if not all([student_id, term, session_year]):
        return jsonify({"error": "Missing parameters"}), 400

    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    # Get fee record
    fee_record = Fee.query.filter_by(
        student_class=student.student_class,
        term=term,
        session=session_year
    ).first()
    total_fee = fee_record.amount if fee_record else 0

    # Get payments for this student in this term/session
    payments = Payment.query.filter_by(
        student_id=student.id,
        term=term,
        session=session_year
    ).order_by(Payment.payment_date).all()

    total_paid = sum(p.amount_paid for p in payments)
    outstanding = total_fee - total_paid

    return jsonify({
        "student": {
            "id": student.id,
            "name": student.name,
            "reg_number": student.reg_number,
            "class": student.student_class,
        },
        "term": term,
        "session": session_year,
        "total_fee": total_fee,
        "total_paid": total_paid,
        "outstanding": outstanding,
        "payments": [
            {
                "id": p.id,
                "amount_paid": p.amount_paid,
                "payment_type": p.payment_type,
                "payment_date": p.payment_date.strftime("%Y-%m-%d"),
            } for p in payments
        ]
    })

# ---------------------------
# FEE MANAGEMENT
# ---------------------------
@app.route("/manage-fees", methods=["GET", "POST"])
def manage_fees():
    if not session.get("admin"):
        return redirect(url_for("index"))

    if request.method == "POST":
        student_class = request.form.get("student_class")
        term = request.form.get("term")
        session_year = request.form.get("session")
        amount = request.form.get("amount")
        
        if not all([student_class, term, session_year, amount]):
            flash("All fields are required.", "error")
            return redirect(url_for("manage_fees"))
        
        try:
            fee_amount = float(amount)
            existing_fee = Fee.query.filter_by(
                student_class=student_class,
                term=term,
                session=session_year
            ).first()
            
            if existing_fee:
                existing_fee.amount = fee_amount
                flash("Fee updated successfully!", "success")
            else:
                new_fee = Fee(
                    student_class=student_class,
                    term=term,
                    session=session_year,
                    amount=fee_amount
                )
                db.session.add(new_fee)
                flash("Fee added successfully!", "success")
            
            db.session.commit()
            
        except ValueError:
            flash("Invalid amount. Please enter a valid number.", "error")
            return redirect(url_for("manage_fees"))

    fees = Fee.query.all()
    return render_template("manage_fees.html", fees=fees)

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
            ).options(joinedload(Student.payments)).all()
    
    return render_template("receipt_generator.html", search_results=search_results)


@app.route("/view-receipt/<int:payment_id>")
def view_receipt(payment_id):
    if not session.get("admin"):
        return redirect(url_for("index"))

    payment = Payment.query.get_or_404(payment_id)
    student = payment.student
    remaining_balance = session.pop('remaining_balance', None)

    if remaining_balance is None:
        total_paid_for_term = db.session.query(db.func.sum(Payment.amount_paid)).filter(
            Payment.student_id == student.id,
            Payment.term == payment.term,
            Payment.session == payment.session
        ).scalar() or 0
        
        fee_record = Fee.query.filter_by(
            student_class=student.student_class,
            term=payment.term,
            session=payment.session
        ).first()
        total_fees = fee_record.amount if fee_record else 0
        remaining_balance = total_fees - total_paid_for_term
        flash("Could not find remaining balance from the form. Calculated balance based on fees.", "warning")

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    if os.path.exists("alfurqan_logo.jpg"):
        p.drawImage("alfurqan_logo.jpg", 50, height - 120, width=80, height=60)

    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, height - 50, "ALFURQAN ACADEMY")
    p.setFont("Helvetica", 10)
    p.drawString(200, height - 65, "Mai’adua | Motto: Academic Excellence")
    p.drawString(200, height - 80, "Tel: 07067702084, 08025076989")

    p.setFont("Helvetica-Bold", 14)
    p.drawString(230, height - 140, "PAYMENT RECEIPT")

    y = height - 180
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Student Name: {student.name}")
    p.drawString(50, y - 20, f"Reg Number: {student.reg_number}")
    p.drawString(50, y - 40, f"Class: {student.student_class}")

    p.drawString(50, y - 80, f"Date: {payment.payment_date.strftime('%Y-%m-%d')}")
    p.drawString(50, y - 100, f"Term: {payment.term}")
    p.drawString(50, y - 120, f"Session: {payment.session}")
    p.drawString(50, y - 140, f"Payment Type: {payment.payment_type}")
    p.drawString(50, y - 160, f"Receipt No: {payment.id}")
    
    y_summary = y - 200
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y_summary, "Financial Summary")
    p.setFont("Helvetica", 12)
    p.drawString(50, y_summary - 20, f"Amount Paid: ₦{payment.amount_paid:,.2f}")
    p.setFont("Helvetica-Bold", 12)
    p.setFillColorRGB(0.8, 0, 0)
    if isinstance(remaining_balance, (float, int)):
        p.drawString(50, y_summary - 40, f"Remaining Balance: ₦{remaining_balance:,.2f}")
    else:
        p.drawString(50, y_summary - 40, f"Remaining Balance: {remaining_balance}")
    p.setFillColorRGB(0, 0, 0)

    p.setFont("Helvetica-Oblique", 10)
    p.drawString(200, 80, "Thank you for your payment!")

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
# ENTRY POINT
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


