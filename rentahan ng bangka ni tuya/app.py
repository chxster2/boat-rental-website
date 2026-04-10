from datetime import datetime, date, time, timedelta
from functools import wraps
import calendar
import os
import random
import string
import uuid

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///boat_rental.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "receipts")
app.config["PROFILE_UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "profiles")
app.config["BOAT_UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "boats")
app.config["CHAT_UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "chat")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    bio = db.Column(db.Text, default="")
    profile_image_path = db.Column(db.String(255))
    last_seen_at = db.Column(db.DateTime, default=datetime.now)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="customer", nullable=False)  # customer, owner, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Boat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    hourly_rate = db.Column(db.Float, nullable=False)
    available_for_fishing = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(255), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Beach(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    boat_id = db.Column(db.Integer, db.ForeignKey("boat.id"), nullable=False)
    beach_id = db.Column(db.Integer, db.ForeignKey("beach.id"), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    booking_time = db.Column(db.Time, nullable=False)
    duration_hours = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, gcash
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="Pending")
    receipt_code = db.Column(db.String(30), nullable=False)
    transaction_receipt_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    seen_at = db.Column(db.DateTime)
    image_path = db.Column(db.String(255))
    like_count = db.Column(db.Integer, default=0)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    boat_id = db.Column(db.Integer, db.ForeignKey("boat.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    channel = db.Column(db.String(10), nullable=False)  # email, sms
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("You are not allowed to access that page.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return wrapper


def generate_receipt():
    chars = string.ascii_uppercase + string.digits
    return "RCPT-" + "".join(random.choice(chars) for _ in range(8))


def ensure_schema_updates():
    # Keep SQLite schema in sync for existing databases.
    cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(booking)")).fetchall()]
    if "transaction_receipt_path" not in cols:
        db.session.execute(db.text("ALTER TABLE booking ADD COLUMN transaction_receipt_path VARCHAR(255)"))
        db.session.commit()
    user_cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(user)")).fetchall()]
    if "profile_image_path" not in user_cols:
        db.session.execute(db.text("ALTER TABLE user ADD COLUMN profile_image_path VARCHAR(255)"))
        db.session.commit()
    if "last_seen_at" not in user_cols:
        db.session.execute(db.text("ALTER TABLE user ADD COLUMN last_seen_at DATETIME"))
        db.session.commit()
    if "bio" not in user_cols:
        db.session.execute(db.text("ALTER TABLE user ADD COLUMN bio TEXT"))
        db.session.commit()
    message_cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(message)")).fetchall()]
    if "seen_at" not in message_cols:
        db.session.execute(db.text("ALTER TABLE message ADD COLUMN seen_at DATETIME"))
        db.session.commit()
    if "image_path" not in message_cols:
        db.session.execute(db.text("ALTER TABLE message ADD COLUMN image_path VARCHAR(255)"))
        db.session.commit()
    if "like_count" not in message_cols:
        db.session.execute(db.text("ALTER TABLE message ADD COLUMN like_count INTEGER DEFAULT 0"))
        db.session.commit()


@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen_at = datetime.now()
        db.session.commit()


def seed_data():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["PROFILE_UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["BOAT_UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["CHAT_UPLOAD_FOLDER"], exist_ok=True)
    if User.query.count() == 0:
        admin = User(full_name="Arvin Chester M. Plata", email="admin@boat.com", phone="09000000001", role="admin")
        admin.set_password("admin123")
        owner = User(full_name="Hanahnea J. Rodriguez", email="owner@boat.com", phone="09000000002", role="owner")
        owner.set_password("owner123")
        customer = User(full_name="Customer 1", email="customer@boat.com", phone="09000000003", role="customer")
        customer.set_password("customer123")
        db.session.add_all([admin, owner, customer])
        db.session.commit()
    else:
        admin = User.query.filter_by(role="admin").first()
        owner = User.query.filter_by(role="owner").first()
        customer = User.query.filter_by(role="customer").order_by(User.id.asc()).first()
        if admin:
            admin.full_name = "Arvin Chester M. Plata"
        if owner:
            owner.full_name = "Hanahnea J. Rodriguez"
        if customer:
            customer.full_name = "Customer 1"
        db.session.commit()

    beaches = [
        ("Fortune Island", "/static/img/fortune-island.png"),
        ("Natipuan", "/static/img/natipuan.png"),
        ("Panutsutan", "/static/img/panutsutan.png"),
        ("Tali Beach", "/static/img/tali-beach.png"),
        ("Twin Island", "/static/img/twin-island.png"),
        ("White Sand", "/static/img/fortune-island.png"),
    ]
    for name, image in beaches:
        beach = Beach.query.filter_by(name=name).first()
        if beach:
            beach.image_url = image
            beach.description = f"Trip destination: {name}"
        else:
            db.session.add(Beach(name=name, image_url=image, description=f"Trip destination: {name}"))
    db.session.commit()

    if Boat.query.count() == 0:
        owner = User.query.filter_by(role="owner").first()
        boats = [
            ("Arvin Chester 44 Small", 18, 2200, True, "Safe and practical boat for short island rides."),
            ("Arvin Chester 44 Big", 30, 3500, True, "Large boat for families and group island hopping."),
            ("Catindig", 22, 2800, True, "Comfortable all-around boat for beach trips and fishing."),
        ]
        default_image = "https://images.unsplash.com/photo-1569263979104-865ab7cd8d13?auto=format&fit=crop&w=900&q=80"
        for item in boats:
            db.session.add(
                Boat(
                    name=item[0],
                    capacity=item[1],
                    hourly_rate=item[2],
                    available_for_fishing=item[3],
                    description=item[4],
                    image_url=default_image,
                    owner_id=owner.id,
                )
            )
        db.session.commit()
    else:
        boats = Boat.query.order_by(Boat.id.asc()).limit(3).all()
        renamed = [
            ("Arvin Chester 44 Small", 18, 2200, True, "Safe and practical boat for short island rides."),
            ("Arvin Chester 44 Big", 30, 3500, True, "Large boat for families and group island hopping."),
            ("Catindig", 22, 2800, True, "Comfortable all-around boat for beach trips and fishing."),
        ]
        for idx, boat in enumerate(boats):
            boat.name = renamed[idx][0]
            boat.capacity = renamed[idx][1]
            boat.hourly_rate = renamed[idx][2]
            boat.available_for_fishing = renamed[idx][3]
            boat.description = renamed[idx][4]
        db.session.commit()


def send_notifications(booking, user):
    msg = f"Booking #{booking.id} for {booking.booking_date} at {booking.booking_time} is confirmed. Receipt: {booking.receipt_code}"
    db.session.add(Notification(user_id=user.id, channel="email", message=msg))
    db.session.add(Notification(user_id=user.id, channel="sms", message=msg))
    db.session.commit()
    print(f"[EMAIL to {user.email}] {msg}")
    print(f"[SMS to {user.phone}] {msg}")


def has_booking_conflict(boat_id, booking_date, booking_time, duration_hours):
    existing = Booking.query.filter_by(boat_id=boat_id, booking_date=booking_date).all()
    start = datetime.combine(booking_date, booking_time)
    end = start + timedelta(hours=duration_hours)
    for booking in existing:
        other_start = datetime.combine(booking.booking_date, booking.booking_time)
        other_end = other_start + timedelta(hours=booking.duration_hours)
        if start < other_end and end > other_start:
            return True
    return False


@app.route("/")
def index():
    boats = Boat.query.all()
    owner_map = {}
    if boats:
        owner_ids = {boat.owner_id for boat in boats}
        owners = User.query.filter(User.id.in_(owner_ids)).all()
        owner_map = {owner.id: owner.full_name for owner in owners}
    beaches = Beach.query.all()
    reviews = (
        db.session.query(Review, User.full_name, Boat.name)
        .join(User, Review.customer_id == User.id)
        .join(Boat, Review.boat_id == Boat.id)
        .order_by(Review.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template("index.html", boats=boats, beaches=beaches, reviews=reviews, owner_map=owner_map)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"].strip().lower()
        phone = request.form["phone"]
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("register"))

        user = User(full_name=full_name, email=email, phone=phone, role="customer")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back!", "success")
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", current_user.full_name).strip() or current_user.full_name
        current_user.phone = request.form.get("phone", current_user.phone).strip() or current_user.phone
        if current_user.role == "owner":
            current_user.bio = request.form.get("bio", "").strip()
        profile_file = request.files.get("profile_image")
        if profile_file and profile_file.filename:
            extension = profile_file.filename.rsplit(".", 1)[-1].lower() if "." in profile_file.filename else ""
            if extension not in {"png", "jpg", "jpeg", "webp"}:
                flash("Profile image must be PNG, JPG, JPEG, or WEBP.", "danger")
                return redirect(url_for("profile"))
            filename = f"user-{current_user.id}-{uuid.uuid4().hex}.{extension}"
            full_path = os.path.join(app.config["PROFILE_UPLOAD_FOLDER"], filename)
            profile_file.save(full_path)
            current_user.profile_image_path = f"/static/uploads/profiles/{filename}"
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))
    owned_boats = []
    if current_user.role == "owner":
        owned_boats = Boat.query.filter_by(owner_id=current_user.id).order_by(Boat.id.desc()).all()
    return render_template("profile.html", owned_boats=owned_boats)


@app.route("/profile/<int:user_id>")
@login_required
def public_profile(user_id):
    user = User.query.get_or_404(user_id)
    owned_boats = []
    if user.role == "owner":
        owned_boats = Boat.query.filter_by(owner_id=user.id).order_by(Boat.id.desc()).all()
    return render_template("profile_public.html", user=user, owned_boats=owned_boats)


@app.route("/owner/boats/add", methods=["POST"])
@login_required
def owner_add_boat():
    if current_user.role != "owner":
        flash("Only owners can add boats.", "danger")
        return redirect(url_for("index"))

    boat_file = request.files.get("boat_image")
    if not boat_file or not boat_file.filename:
        flash("Boat image is required.", "danger")
        return redirect(url_for("profile"))
    extension = boat_file.filename.rsplit(".", 1)[-1].lower() if "." in boat_file.filename else ""
    if extension not in {"png", "jpg", "jpeg", "webp"}:
        flash("Boat image must be PNG, JPG, JPEG, or WEBP.", "danger")
        return redirect(url_for("profile"))
    filename = f"boat-owner-{uuid.uuid4().hex}.{extension}"
    full_path = os.path.join(app.config["BOAT_UPLOAD_FOLDER"], filename)
    boat_file.save(full_path)

    boat = Boat(
        name=request.form["name"],
        capacity=int(request.form["capacity"]),
        hourly_rate=float(request.form["hourly_rate"]),
        available_for_fishing=request.form.get("available_for_fishing") == "on",
        description=request.form.get("description", ""),
        image_url=f"/static/uploads/boats/{filename}",
        owner_id=current_user.id,
    )
    db.session.add(boat)
    db.session.commit()
    flash("Boat added successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/boats")
def boats():
    all_boats = Boat.query.all()
    owner_map = {}
    if all_boats:
        owner_ids = {boat.owner_id for boat in all_boats}
        owners = User.query.filter(User.id.in_(owner_ids)).all()
        owner_map = {owner.id: owner.full_name for owner in owners}
    return render_template("boats.html", boats=all_boats, owner_map=owner_map)


@app.route("/book", methods=["GET", "POST"])
@login_required
def book():
    if current_user.role == "admin":
        flash("This account type cannot create bookings.", "warning")
        return redirect(url_for("admin_bookings"))
    if current_user.role == "owner":
        flash("This account type cannot create bookings.", "warning")
        return redirect(url_for("owner_booked_boats"))

    boats = Boat.query.all()
    beaches = Beach.query.all()
    if request.method == "POST":
        boat_id = int(request.form["boat_id"])
        beach_id = int(request.form["beach_id"])
        booking_date = datetime.strptime(request.form["booking_date"], "%Y-%m-%d").date()
        booking_time = datetime.strptime(request.form["booking_time"], "%H:%M").time()
        duration_hours = int(request.form["duration_hours"])
        payment_method = request.form["payment_method"]
        trip_type = request.form["trip_type"]
        addon_package = request.form.get("addon_package") == "on"
        notes = request.form.get("notes", "")
        gcash_receipt = request.files.get("gcash_receipt")

        # Automated scheduling rules
        if booking_date < date.today():
            flash("Booking date cannot be in the past.", "danger")
            return redirect(url_for("book"))
        if booking_time < time(6, 0) or booking_time > time(18, 0):
            flash("Bookings must start between 6:00 AM and 6:00 PM.", "danger")
            return redirect(url_for("book"))
        if duration_hours < 1 or duration_hours > 12:
            flash("Duration must be from 1 to 12 hours.", "danger")
            return redirect(url_for("book"))
        if has_booking_conflict(boat_id, booking_date, booking_time, duration_hours):
            flash("Schedule conflict: this boat is already booked in that time window.", "danger")
            return redirect(url_for("book"))
        if payment_method == "gcash" and (not gcash_receipt or not gcash_receipt.filename):
            flash("Please upload your GCash transaction screenshot.", "danger")
            return redirect(url_for("book"))

        saved_receipt_path = None
        if gcash_receipt and gcash_receipt.filename:
            extension = gcash_receipt.filename.rsplit(".", 1)[-1].lower() if "." in gcash_receipt.filename else ""
            if extension not in {"png", "jpg", "jpeg", "webp"}:
                flash("Receipt upload must be PNG, JPG, JPEG, or WEBP.", "danger")
                return redirect(url_for("book"))
            filename = f"{uuid.uuid4().hex}.{extension}"
            full_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            gcash_receipt.save(full_path)
            saved_receipt_path = f"/static/uploads/receipts/{filename}"

        boat = db.session.get(Boat, boat_id)
        total_price = boat.hourly_rate * duration_hours
        if addon_package:
            total_price += 3000
        extra_notes = f"Trip Type: {trip_type} | Add-ons: {'Island Hopping + Fish Feeding (+3000)' if addon_package else 'None'}"
        notes = f"{extra_notes}\n{notes}".strip()
        booking = Booking(
            customer_id=current_user.id,
            boat_id=boat_id,
            beach_id=beach_id,
            booking_date=booking_date,
            booking_time=booking_time,
            duration_hours=duration_hours,
            payment_method=payment_method,
            total_price=total_price,
            notes=notes,
            status="Confirmed",
            receipt_code=generate_receipt(),
            transaction_receipt_path=saved_receipt_path,
        )
        db.session.add(booking)
        db.session.commit()

        send_notifications(booking, current_user)

        flash("Booking confirmed! Receipt generated.", "success")
        return redirect(url_for("receipt", booking_id=booking.id))

    return render_template("book.html", boats=boats, beaches=beaches)


@app.route("/my-bookings")
@login_required
def my_bookings():
    if current_user.role == "admin":
        return redirect(url_for("admin_bookings"))
    if current_user.role == "owner":
        return redirect(url_for("owner_booked_boats"))

    results = (
        db.session.query(Booking, Boat.name, Beach.name.label("beach_name"))
        .join(Boat, Booking.boat_id == Boat.id)
        .join(Beach, Booking.beach_id == Beach.id)
        .filter(Booking.customer_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template("my_bookings.html", rows=results)


@app.route("/owner/booked-boats")
@login_required
def owner_booked_boats():
    if current_user.role != "owner":
        flash("Only owners can access booked boats.", "danger")
        return redirect(url_for("index"))
    rows = (
        db.session.query(
            Booking,
            User.full_name.label("customer_name"),
            Boat.name.label("boat_name"),
            Beach.name.label("beach_name"),
        )
        .join(User, Booking.customer_id == User.id)
        .join(Boat, Booking.boat_id == Boat.id)
        .join(Beach, Booking.beach_id == Beach.id)
        .filter(Boat.owner_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template("owner_booked_boats.html", rows=rows)


@app.route("/admin/bookings")
@login_required
@admin_required
def admin_bookings():
    rows = (
        db.session.query(
            Booking,
            User.full_name.label("customer_name"),
            Boat.name.label("boat_name"),
            Beach.name.label("beach_name"),
        )
        .join(User, Booking.customer_id == User.id)
        .join(Boat, Booking.boat_id == Boat.id)
        .join(Beach, Booking.beach_id == Beach.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template("admin_bookings.html", rows=rows)


@app.route("/receipt/<int:booking_id>")
@login_required
def receipt(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.customer_id != current_user.id:
        flash("Receipt not found.", "danger")
        return redirect(url_for("my_bookings"))
    boat = db.session.get(Boat, booking.boat_id)
    beach = db.session.get(Beach, booking.beach_id)
    return render_template("receipt.html", booking=booking, boat=boat, beach=beach)


@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    target_user_id = request.args.get("contact_id", type=int)

    if current_user.role == "admin":
        contacts = User.query.filter(User.id != current_user.id, User.role == "owner").order_by(User.full_name.asc()).all()
    elif current_user.role == "owner":
        contacts = (
            User.query.filter(User.id != current_user.id, User.role.in_(("customer", "admin")))
            .order_by(User.role.asc(), User.full_name.asc())
            .all()
        )
    else:
        contacts = User.query.filter_by(role="owner").order_by(User.full_name.asc()).all()

    if contacts and target_user_id is None:
        target_user_id = contacts[0].id
    elif not contacts:
        target_user_id = None

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        send_like = request.form.get("send_like") == "1"
        posted_target = request.form.get("target_user_id", type=int)
        image_file = request.files.get("chat_image")
        if send_like:
            content = "👍"
        if content or (image_file and image_file.filename):
            receiver_id = posted_target if posted_target else target_user_id

            if receiver_id:
                receiver = db.session.get(User, receiver_id)
                if current_user.role == "admin" and receiver and receiver.role == "customer":
                    flash("Admin cannot chat customers.", "danger")
                    return redirect(url_for("chat"))
                if current_user.role == "customer" and receiver and receiver.role == "admin":
                    flash("Customers cannot chat admin.", "danger")
                    return redirect(url_for("chat"))

                image_path = None
                if image_file and image_file.filename:
                    extension = image_file.filename.rsplit(".", 1)[-1].lower() if "." in image_file.filename else ""
                    if extension not in {"png", "jpg", "jpeg", "webp"}:
                        flash("Chat image must be PNG, JPG, JPEG, or WEBP.", "danger")
                        return redirect(url_for("chat", contact_id=receiver_id))
                    filename = f"chat-{uuid.uuid4().hex}.{extension}"
                    full_path = os.path.join(app.config["CHAT_UPLOAD_FOLDER"], filename)
                    image_file.save(full_path)
                    image_path = f"/static/uploads/chat/{filename}"

                db.session.add(
                    Message(
                        sender_id=current_user.id,
                        receiver_id=receiver_id,
                        content=content if content else "[Image]",
                        image_path=image_path,
                    )
                )
                db.session.commit()
                flash("Message sent.", "success")
                return redirect(url_for("chat", contact_id=receiver_id))

    messages = []
    if target_user_id:
        Message.query.filter_by(sender_id=target_user_id, receiver_id=current_user.id, seen_at=None).update(
            {"seen_at": datetime.now()}, synchronize_session=False
        )
        db.session.commit()
        messages = (
            Message.query.filter(
                ((Message.sender_id == current_user.id) & (Message.receiver_id == target_user_id))
                | ((Message.sender_id == target_user_id) & (Message.receiver_id == current_user.id))
            )
            .order_by(Message.created_at.asc())
            .all()
        )
    unread_counts = dict(
        db.session.query(Message.sender_id, db.func.count(Message.id))
        .filter(Message.receiver_id == current_user.id, Message.seen_at.is_(None))
        .group_by(Message.sender_id)
        .all()
    )
    conversation_preview = {}
    for contact in contacts:
        latest = (
            Message.query.filter(
                ((Message.sender_id == current_user.id) & (Message.receiver_id == contact.id))
                | ((Message.sender_id == contact.id) & (Message.receiver_id == current_user.id))
            )
            .order_by(Message.created_at.desc())
            .first()
        )
        if latest:
            preview = "Photo" if latest.image_path and latest.content == "[Image]" else latest.content
            elapsed_mins = int((datetime.now() - latest.created_at).total_seconds() // 60)
            time_tag = f"{elapsed_mins}m" if elapsed_mins < 60 else f"{elapsed_mins // 60}h"
            conversation_preview[contact.id] = {"text": preview[:35], "time_tag": time_tag}
        else:
            conversation_preview[contact.id] = {"text": "", "time_tag": ""}
    selected_contact = None
    status_text = "Offline"
    if target_user_id:
        selected_contact = next((c for c in contacts if c.id == target_user_id), None)
        if selected_contact and selected_contact.last_seen_at:
            diff = datetime.now() - selected_contact.last_seen_at
            if diff.total_seconds() <= 120:
                status_text = "Online"
            else:
                mins = int(diff.total_seconds() // 60)
                if mins >= 60:
                    hours = mins // 60
                    status_text = f"Last active {hours} hour(s) ago"
                else:
                    status_text = f"Last active {mins} min ago"

    return render_template(
        "chat.html",
        messages=messages,
        contacts=contacts,
        target_user_id=target_user_id,
        selected_contact=selected_contact,
        status_text=status_text,
        unread_counts=unread_counts,
        conversation_preview=conversation_preview,
    )


@app.route("/chat/message/<int:message_id>/like", methods=["POST"])
@login_required
def like_message(message_id):
    msg = Message.query.get_or_404(message_id)
    if current_user.id not in (msg.sender_id, msg.receiver_id):
        flash("Not allowed.", "danger")
        return redirect(url_for("chat"))
    msg.like_count = (msg.like_count or 0) + 1
    db.session.commit()
    other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
    return redirect(url_for("chat", contact_id=other_id))


@app.route("/reviews", methods=["GET", "POST"])
@login_required
def reviews():
    boats = Boat.query.all()
    if request.method == "POST":
        if current_user.role != "customer":
            flash("Only customers can post reviews.", "danger")
            return redirect(url_for("reviews"))
        rating = int(request.form["rating"])
        boat_id = int(request.form["boat_id"])
        comment = request.form.get("comment", "")
        if rating < 1 or rating > 5:
            flash("Rating must be from 1 to 5.", "danger")
            return redirect(url_for("reviews"))
        db.session.add(Review(customer_id=current_user.id, boat_id=boat_id, rating=rating, comment=comment))
        db.session.commit()
        flash("Review submitted. Thank you!", "success")
        return redirect(url_for("reviews"))

    all_reviews = (
        db.session.query(Review, User.full_name, Boat.name)
        .join(User, Review.customer_id == User.id)
        .join(Boat, Review.boat_id == Boat.id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return render_template("reviews.html", boats=boats, all_reviews=all_reviews)


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    boats = Boat.query.order_by(Boat.id.desc()).all()
    owners = User.query.filter_by(role="owner").order_by(User.full_name.asc()).all()
    owner_map = {owner.id: owner.full_name for owner in owners}
    total_bookings = Booking.query.count()
    total_earnings = db.session.query(db.func.coalesce(db.func.sum(Booking.total_price), 0)).scalar()
    today_bookings = Booking.query.filter_by(booking_date=date.today()).count()
    boats_count = Boat.query.count()

    today = date.today()
    month_days = calendar.monthcalendar(today.year, today.month)
    fully_booked_days = set()
    counts = (
        db.session.query(Booking.booking_date, db.func.count(Booking.id))
        .filter(db.extract("year", Booking.booking_date) == today.year)
        .filter(db.extract("month", Booking.booking_date) == today.month)
        .group_by(Booking.booking_date)
        .all()
    )
    for booked_date, count in counts:
        if boats_count > 0 and count >= boats_count:
            fully_booked_days.add(booked_date.day)

    return render_template(
        "admin_dashboard.html",
        boats=boats,
        owners=owners,
        owner_map=owner_map,
        total_bookings=total_bookings,
        total_earnings=total_earnings,
        today_bookings=today_bookings,
        month_days=month_days,
        month_name=today.strftime("%B %Y"),
        fully_booked_days=fully_booked_days,
    )


@app.route("/admin/boats/add", methods=["POST"])
@login_required
@admin_required
def admin_add_boat():
    owner_id = int(request.form["owner_id"])
    boat_file = request.files.get("boat_image")
    if not boat_file or not boat_file.filename:
        flash("Boat image file is required.", "danger")
        return redirect(url_for("admin_dashboard"))
    extension = boat_file.filename.rsplit(".", 1)[-1].lower() if "." in boat_file.filename else ""
    if extension not in {"png", "jpg", "jpeg", "webp"}:
        flash("Boat image must be PNG, JPG, JPEG, or WEBP.", "danger")
        return redirect(url_for("admin_dashboard"))
    filename = f"boat-admin-{uuid.uuid4().hex}.{extension}"
    full_path = os.path.join(app.config["BOAT_UPLOAD_FOLDER"], filename)
    boat_file.save(full_path)
    boat_image_url = f"/static/uploads/boats/{filename}"
    boat = Boat(
        name=request.form["name"],
        capacity=int(request.form["capacity"]),
        hourly_rate=float(request.form["hourly_rate"]),
        available_for_fishing=request.form.get("available_for_fishing") == "on",
        description=request.form.get("description", ""),
        image_url=boat_image_url,
        owner_id=owner_id,
    )
    db.session.add(boat)
    db.session.commit()
    flash("Boat added successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/boats/<int:boat_id>/delete")
@login_required
@admin_required
def admin_delete_boat(boat_id):
    boat = db.session.get(Boat, boat_id)
    if boat:
        db.session.delete(boat)
        db.session.commit()
        flash("Boat deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/owner/fleet")
@login_required
def owner_fleet():
    if current_user.role != "owner":
        flash("Only owners can access fleet management.", "danger")
        return redirect(url_for("index"))
    boats = Boat.query.filter_by(owner_id=current_user.id).order_by(Boat.id.desc()).all()
    return render_template("owner_fleet.html", boats=boats)


@app.route("/owner/boats/<int:boat_id>/photo", methods=["POST"])
@login_required
def owner_update_boat_photo(boat_id):
    if current_user.role != "owner":
        flash("Only owners can update boat photos.", "danger")
        return redirect(url_for("index"))

    boat = Boat.query.get_or_404(boat_id)
    if boat.owner_id != current_user.id:
        flash("You can only update your own boats.", "danger")
        return redirect(url_for("profile"))

    boat_file = request.files.get("boat_image")
    if not boat_file or not boat_file.filename:
        flash("Please choose an image file.", "warning")
        return redirect(url_for("profile"))

    extension = boat_file.filename.rsplit(".", 1)[-1].lower() if "." in boat_file.filename else ""
    if extension not in {"png", "jpg", "jpeg", "webp"}:
        flash("Boat image must be PNG, JPG, JPEG, or WEBP.", "danger")
        return redirect(url_for("profile"))

    filename = f"boat-{boat.id}-{uuid.uuid4().hex}.{extension}"
    full_path = os.path.join(app.config["BOAT_UPLOAD_FOLDER"], filename)
    boat_file.save(full_path)
    boat.image_url = f"/static/uploads/boats/{filename}"
    db.session.commit()
    flash("Boat photo updated successfully.", "success")
    return redirect(url_for("profile"))


@app.context_processor
def inject_counts():
    if current_user.is_authenticated:
        notif_count = Notification.query.filter_by(user_id=current_user.id).count()
        chat_notif_count = (
            db.session.query(db.func.count(Message.id))
            .filter(Message.receiver_id == current_user.id, Message.seen_at.is_(None))
            .scalar()
        )
        return {"notif_count": notif_count, "chat_notif_count": chat_notif_count}
    return {"notif_count": 0, "chat_notif_count": 0}


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        seed_data()
    app.run(debug=True)
