from flask import (
    Flask, flash, render_template, request,
    redirect, session, url_for
)
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import secrets
import re
from sqlalchemy import inspect

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")


app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}?"
    "ssl_verify_cert=true&ssl_verify_identity=true"
)


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------------- DATABASE MODELS ----------------

class canteen(db.Model):
    __tablename__ = "canteen"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="customer", nullable=False)


class CartModel(db.Model):
    __tablename__ = "carts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)

    items = db.relationship(
        "CartItem",
        backref="cart",
        cascade="all, delete-orphan"
    )


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id"), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    total_amount = db.Column(db.Float, nullable=False)
    phone_number = db.Column(db.String(15), nullable=True)

    pickup_code = db.Column(
        db.String(20),
        unique=True,
        nullable=True
    )

    order_status = db.Column(
        db.String(30),
        default="confirmed",
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    collected_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="orders")

    items = db.relationship(
        "OrderItem",
        backref="order",
        cascade="all, delete-orphan"
    )


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False
    )

    item_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        unique=True
    )

    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)

    payment_status = db.Column(
        db.String(30),
        default="pending",
        nullable=False
    )

    transaction_reference = db.Column(db.String(150))
    paid_at = db.Column(db.DateTime)

    order = db.relationship(
        "Order",
        backref=db.backref("payment", uselist=False)
    )


# ---------------- ROLE HELPER ----------------

def get_logged_in_user():
    if "user_id" not in session:
        return None

    return db.session.get(User, session["user_id"])


def has_authority_access(user):
    return user and user.role in ["owner", "salesman", "authority"]


# ---------------- CART HELPER ----------------

def get_active_cart(user_id):

    cart = CartModel.query.filter_by(
        user_id=user_id,
        status="active"
    ).first()

    if cart is None:

        cart = CartModel(
            user_id=user_id,
            status="active"
        )

        db.session.add(cart)
        db.session.flush()

    return cart


# ---------------- PICKUP CODE GENERATOR ----------------

def generate_pickup_code():

    while True:

        number = secrets.randbelow(900000) + 100000
        code = f"CAN-{number}"

        existing = Order.query.filter_by(
            pickup_code=code
        ).first()

        if not existing:
            return code


# ---------------- FOOD ITEMS ----------------

FOOD_ITEMS = {
    1: ("Chicken Biryani", 160),
    2: ("Mutton Biryani", 220),
    3: ("Veg Biryani", 120),
    4: ("Hyderabadi Biryani", 180),
    5: ("Chicken Dum Biryani", 190),
    6: ("Paneer Biryani", 150),
    7: ("Egg Biryani", 130),
    8: ("Fish Biryani", 200),
    9: ("Mushroom Biryani", 140),
    10: ("Prawns Biryani", 230),
    11: ("Veg Hakka Noodles", 80),
    12: ("Chicken Noodles", 120),
    13: ("Schezwan Noodles", 100),
    14: ("Egg Noodles", 90),
    15: ("Chilli Garlic Noodles", 100),
    16: ("Singapore Noodles", 130),
    17: ("Paneer Noodles", 110),
    18: ("Mixed Noodles", 150),
    19: ("Manchurian Noodles", 120),
    20: ("Mushroom Noodles", 110),
    21: ("Samosa", 20),
    22: ("Onion Pakoda", 40),
    23: ("Spring Rolls", 60),
    24: ("Bread Pizza", 50),
    25: ("French Fries", 70),
    26: ("Mirchi Bajji", 30),
    27: ("Chicken Nuggets", 90),
    28: ("Chicken 65", 120),
    29: ("Veg Cutlet", 40),
    30: ("Paneer Pakoda", 80),
    31: ("Chicken 65", 120),
    32: ("Chilli Chicken", 140),
    33: ("Chicken Lollipop", 150),
    34: ("Paneer Tikka", 130),
    35: ("Veg Manchurian", 100),
    36: ("Gobi Manchurian", 90),
    37: ("Crispy Corn", 100),
    38: ("French Fries", 70),
    39: ("Cheese Balls", 110),
    40: ("Paneer Pakoda", 80)
}


# ---------------- HOME AND FOOD PAGES ----------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/menu")
def menu():
    return render_template("menu.html")


@app.route("/biryani")
def biryani():
    return render_template("food/biryani.html")


@app.route("/noodles")
def noodles():
    return render_template("food/noodles.html")


@app.route("/snacks")
def snacks():
    return render_template("food/snacks.html")


@app.route("/starters")
def starters():
    return render_template("food/starter.html")


# ---------------- SIGNUP ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        phone_number = request.form["phone_number"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:

            return render_template(
                "authority/signup.html",
                error="Passwords do not match."
            )

        existing_user = User.query.filter(
            (User.email == email) |
            (User.phone_number == phone_number) |
            (User.username == username)
        ).first()

        if existing_user:

            return render_template(
                "authority/signup.html",
                error="Username, email or phone number already exists."
            )

        new_user = User(
            username=username,
            email=email,
            phone_number=phone_number,
            password=password,
            role="customer"
        )

        try:

            db.session.add(new_user)
            db.session.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except Exception as e:

            db.session.rollback()
            print("Signup error:", repr(e))

            flash("Registration failed.", "danger")

    return render_template("authority/signup.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and user.password == password:

            session.clear()

            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            guest_cart = session.get("cart", {})
            confirm_after_login = session.get("confirm_after_login", False)

            try:

                # Transfer guest cart only to customer accounts

                if guest_cart and user.role == "customer":

                    cart = get_active_cart(user.id)

                    for item_id, item in guest_cart.items():

                        existing_item = CartItem.query.filter_by(
                            cart_id=cart.id,
                            item_id=int(item_id)
                        ).first()

                        if existing_item:

                            existing_item.quantity += item["quantity"]

                        else:

                            new_item = CartItem(
                                cart_id=cart.id,
                                item_id=int(item_id),
                                name=item["name"],
                                price=item["price"],
                                quantity=item["quantity"]
                            )

                            db.session.add(new_item)

                    db.session.commit()

                session.pop("cart", None)

                # OWNER AND SALESMAN

                if user.role in ["owner", "salesman", "authority"]:

                    return redirect(
                        url_for("authority_dashboard")
                    )

                # CUSTOMER

                if confirm_after_login:

                    return redirect(
                        url_for("confirm_order")
                    )

                return redirect(url_for("index"))

            except Exception as e:

                db.session.rollback()

                print("Login error:", repr(e))

                flash(
                    "Unable to transfer cart.",
                    "danger"
                )

                return redirect(url_for("view_cart"))

        return render_template(
            "authority/login.html",
            error="Invalid email or password."
        )

    return render_template("authority/login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have logged out successfully.",
        "success"
    )

    return redirect(url_for("index"))


# ---------------- ADD TO CART ----------------

@app.route("/add_to_cart/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):

    if item_id not in FOOD_ITEMS:

        flash("Food item not found.", "danger")
        return redirect(url_for("menu"))

    name, price = FOOD_ITEMS[item_id]

    if "user_id" in session:

        user = get_logged_in_user()

        if not user or user.role != "customer":
            flash("Only customers can add food to the cart.", "warning")
            return redirect(url_for("menu"))

        try:

            cart = get_active_cart(user.id)

            existing_item = CartItem.query.filter_by(
                cart_id=cart.id,
                item_id=item_id
            ).first()

            if existing_item:

                existing_item.quantity += 1

            else:

                new_item = CartItem(
                    cart_id=cart.id,
                    item_id=item_id,
                    name=name,
                    price=price,
                    quantity=1
                )

                db.session.add(new_item)

            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print("Add cart error:", repr(e))

            flash(
                "Unable to add item to cart.",
                "danger"
            )

            return redirect(url_for("menu"))

    else:

        guest_cart = session.get("cart", {})
        key = str(item_id)

        if key in guest_cart:

            guest_cart[key]["quantity"] += 1

        else:

            guest_cart[key] = {
                "name": name,
                "price": price,
                "quantity": 1
            }

        session["cart"] = guest_cart

    flash(
        f"{name} added to cart.",
        "success"
    )

    return redirect(request.referrer or url_for("menu"))


# ---------------- VIEW CART ----------------

@app.route("/cart")
def view_cart():

    cart_items = []
    total = 0

    if "user_id" in session:

        user = get_logged_in_user()

        if user and user.role == "customer":

            cart = CartModel.query.filter_by(
                user_id=user.id,
                status="active"
            ).first()

            if cart:

                cart_items = cart.items

                for item in cart_items:
                    total += item.price * item.quantity

    else:

        guest_cart = session.get("cart", {})

        for item_id, item in guest_cart.items():

            cart_items.append({
                "item_id": int(item_id),
                "name": item["name"],
                "price": item["price"],
                "quantity": item["quantity"],
                "subtotal": item["price"] * item["quantity"]
            })

            total += item["price"] * item["quantity"]

    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total
    )


# ---------------- UPDATE CART ----------------

@app.route("/update_cart/<int:item_id>", methods=["POST"])
def update_cart(item_id):

    try:

        quantity = int(request.form.get("quantity", 1))

        if quantity < 1:

            flash(
                "Quantity must be at least 1.",
                "warning"
            )

            return redirect(url_for("view_cart"))

        if "user_id" in session:

            user = get_logged_in_user()

            if not user or user.role != "customer":
                return "Access Denied!", 403

            cart = CartModel.query.filter_by(
                user_id=user.id,
                status="active"
            ).first()

            if cart:

                item = CartItem.query.filter_by(
                    cart_id=cart.id,
                    item_id=item_id
                ).first()

                if item:
                    item.quantity = quantity
                    db.session.commit()

        else:

            guest_cart = session.get("cart", {})
            key = str(item_id)

            if key in guest_cart:

                guest_cart[key]["quantity"] = quantity
                session["cart"] = guest_cart

    except ValueError:

        flash(
            "Enter a valid quantity.",
            "danger"
        )

    except Exception as e:

        db.session.rollback()

        print("Update cart error:", repr(e))

        flash(
            "Unable to update quantity.",
            "danger"
        )

    return redirect(url_for("view_cart"))


# ---------------- REMOVE FROM CART ----------------

@app.route("/remove_from_cart/<int:item_id>", methods=["POST"])
def remove_from_cart(item_id):

    if "user_id" in session:

        user = get_logged_in_user()

        if not user or user.role != "customer":
            return "Access Denied!", 403

        cart = CartModel.query.filter_by(
            user_id=user.id,
            status="active"
        ).first()

        if cart:

            item = CartItem.query.filter_by(
                cart_id=cart.id,
                item_id=item_id
            ).first()

            if item:

                db.session.delete(item)
                db.session.commit()

    else:

        guest_cart = session.get("cart", {})
        guest_cart.pop(str(item_id), None)
        session["cart"] = guest_cart

    flash(
        "Item removed from cart.",
        "success"
    )

    return redirect(url_for("view_cart"))


# ---------------- CONFIRM COD ORDER ----------------

@app.route("/confirm_order", methods=["GET", "POST"])
def confirm_order():

    if "user_id" not in session:

        session["confirm_after_login"] = True

        return redirect(url_for("login"))

    user = get_logged_in_user()

    if not user or user.role != "customer":
        return "Only customers can confirm orders.", 403

    cart = CartModel.query.filter_by(
        user_id=user.id,
        status="active"
    ).first()

    if not cart or not cart.items:

        flash(
            "Your cart is empty.",
            "warning"
        )

        return redirect(url_for("view_cart"))

    total = sum(
        float(item.price) * item.quantity
        for item in cart.items
    )

    if request.method == "POST":

        phone_number = request.form.get(
            "phone_number",
            ""
        ).strip()

        if not re.fullmatch(r"[6-9]\d{9}", phone_number):

            flash(
                "Enter a valid 10-digit mobile number.",
                "danger"
            )

            return redirect(url_for("confirm_order"))

        try:

            pickup_code = generate_pickup_code()

            new_order = Order(
                user_id=user.id,
                total_amount=total,
                phone_number=phone_number,
                pickup_code=pickup_code,
                order_status="confirmed"
            )

            db.session.add(new_order)
            db.session.flush()

            for item in cart.items:

                order_item = OrderItem(
                    order_id=new_order.id,
                    item_id=item.item_id,
                    name=item.name,
                    quantity=item.quantity,
                    price=item.price,
                    subtotal=float(item.price) * item.quantity
                )

                db.session.add(order_item)

            payment = Payment(
                order_id=new_order.id,
                amount=total,
                payment_method="COD",
                payment_status="pending"
            )

            db.session.add(payment)

            cart.status = "completed"

            db.session.commit()

            flash(
                "Order confirmed successfully!",
                "success"
            )

            return redirect(
                url_for(
                    "order_details",
                    order_id=new_order.id
                )
            )

        except Exception as e:

            db.session.rollback()

            print("Order creation error:", repr(e))

            flash(
                "Unable to confirm your order.",
                "danger"
            )

            return redirect(url_for("view_cart"))

    return render_template(
        "payment.html",
        cart_items=cart.items,
        total=total,
        user=user
    )


# ---------------- ORDER DETAILS ----------------

@app.route("/order/<int:order_id>")
def order_details(order_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    order = Order.query.filter_by(
        id=order_id,
        user_id=session["user_id"]
    ).first_or_404()

    return render_template(
        "order_successful.html",
        order=order
    )


# ---------------- CUSTOMER ORDER HISTORY ----------------

@app.route("/my_orders")
def my_orders():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_logged_in_user()

    if not user or user.role != "customer":
        return "Access Denied!", 403

    orders = Order.query.filter_by(
        user_id=user.id
    ).order_by(
        Order.created_at.desc()
    ).all()

    return render_template(
        "my_orders.html",
        orders=orders
    )


# ---------------- AUTHORITY DASHBOARD ----------------

@app.route("/authority/dashboard")
def authority_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_logged_in_user()

    if not has_authority_access(user):
        return "Access Denied! Authority only.", 403

    orders = Order.query.order_by(
        Order.created_at.desc()
    ).all()

    total_sales = sum(
        order.total_amount
        for order in orders
        if order.payment
        and order.payment.payment_status == "paid"
    )

    total_items_sold = sum(
        item.quantity
        for order in orders
        for item in order.items
        if order.payment
        and order.payment.payment_status == "paid"
    )

    pending_orders = sum(
        1
        for order in orders
        if order.payment
        and order.payment.payment_status == "pending"
    )

    return render_template(
        "authority/dashboard.html",
        orders=orders,
        total_sales=total_sales,
        total_items_sold=total_items_sold,
        pending_orders=pending_orders
    )


# ---------------- ADD SALESMAN ----------------

@app.route("/authority/add_salesman", methods=["GET", "POST"])
def add_salesman():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_logged_in_user()

    if not user or user.role != "owner":
        return "Access Denied! Owner only.", 403

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip()

        phone_number = request.form.get(
            "phone_number", ""
        ).strip()

        password = request.form.get("password", "")

        if not username or not email or not phone_number or not password:

            flash(
                "All fields are required.",
                "danger"
            )

            return redirect(url_for("add_salesman"))

        if not re.fullmatch(r"[6-9]\d{9}", phone_number):

            flash(
                "Enter a valid 10-digit mobile number.",
                "danger"
            )

            return redirect(url_for("add_salesman"))

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "danger"
            )

            return redirect(url_for("add_salesman"))

        existing_user = User.query.filter(
            (User.username == username) |
            (User.email == email) |
            (User.phone_number == phone_number)
        ).first()

        if existing_user:

            flash(
                "Username, email or mobile number already exists.",
                "danger"
            )

            return redirect(url_for("add_salesman"))

        new_salesman = User(
            username=username,
            email=email,
            phone_number=phone_number,
            password=password,
            role="salesman"
        )

        try:

            db.session.add(new_salesman)
            db.session.commit()

            flash(
                "New salesman created successfully!",
                "success"
            )

            return redirect(url_for("authority_dashboard"))

        except Exception as e:

            db.session.rollback()

            print("Salesman creation error:", repr(e))

            flash(
                "Unable to create salesman.",
                "danger"
            )

    return render_template("authority/add_salesman.html")


# ---------------- AUTHORITY COLLECT ORDER ----------------

@app.route("/authority/collect_order", methods=["GET", "POST"])
def collect_order():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_logged_in_user()

    if not has_authority_access(user):
        return "Access Denied! Authority only.", 403

    if request.method == "POST":

        pickup_code = request.form.get(
            "pickup_code",
            ""
        ).strip().upper()

        order = Order.query.filter_by(
            pickup_code=pickup_code
        ).first()

        if not order:

            flash(
                "Invalid pickup code.",
                "danger"
            )

            return redirect(url_for("collect_order"))

        payment = Payment.query.filter_by(
            order_id=order.id
        ).first()

        if not payment:

            flash(
                "Payment record not found.",
                "danger"
            )

            return redirect(url_for("collect_order"))

        if payment.payment_status == "paid":

            flash(
                "This order is already paid and collected.",
                "warning"
            )

            return redirect(url_for("collect_order"))

        if order.order_status != "confirmed":

            flash(
                "This order cannot be collected.",
                "warning"
            )

            return redirect(url_for("collect_order"))

        try:

            payment.payment_status = "paid"
            payment.paid_at = datetime.utcnow()

            order.order_status = "collected"
            order.collected_at = datetime.utcnow()

            db.session.commit()

            flash(
                f"Order {pickup_code} collected successfully. Payment marked as paid.",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            print("Collection error:", repr(e))

            flash(
                "Unable to update order.",
                "danger"
            )

        return redirect(url_for("collect_order"))

    return render_template(
        "authority/collect_order.html"
    )
# ---------------- DATABASE DIAGNOSTICS ----------------

try:
    with app.app_context():

        print("\n========== DATABASE DIAGNOSTICS ==========", flush=True)

        # Check database connection details
        print("Database Host:", db.engine.url.host, flush=True)
        print("Database Port:", db.engine.url.port, flush=True)
        print("Database Name:", db.engine.url.database, flush=True)

        # Check registered SQLAlchemy models
        print(
            "Registered Models:",
            list(db.metadata.tables.keys()),
            flush=True
        )

        print("Starting db.create_all()...", flush=True)

        # Create database tables
        db.create_all()

        print("db.create_all() completed successfully!", flush=True)

        # Check tables actually present in TiDB
        inspector = inspect(db.engine)

        tables = inspector.get_table_names()

        print("Tables Found:", tables, flush=True)

        print("========== DIAGNOSTICS COMPLETED ==========\n", flush=True)

except Exception:

    app.logger.exception("DATABASE TABLE CREATION FAILED")

    raise


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True)
