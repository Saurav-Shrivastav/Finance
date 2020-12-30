import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = db.execute(
        "SELECT * FROM users WHERE id = :id",
        id=session["user_id"]
    )
    purchases = db.execute(
        "SELECT * FROM purchases WHERE user_id = :id",
        id=session["user_id"]
    )
    print(purchases)
    return render_template(
        "portfolio.html",
        cash=user[0]["cash"],
        purchases=purchases
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        
        if not request.form.get('symbol'):
            return apology("must provide Symbol", 403)

        if not request.form.get('shares'):
            return apology("must provide a positive number of shares", 403)
            
        if int(request.form.get('shares')) <= 0:
            return apology("must provide a positive number of shares", 403)

        quoted_data = lookup(request.form.get("symbol"))
        if quoted_data is None:
            return apology("Invalid symbol", 403)

        user = db.execute(
            "SELECT * FROM users WHERE id = :id",
            id=session["user_id"]
        )
        if quoted_data["price"] * int(request.form.get("shares")) > user[0]["cash"]:
            return apology("You can't afford the purchase", 403)

        # Add a purchase
        purchase = db.execute(
            """
                INSERT INTO purchases (user_id, symbol, name, shares, price, total)
                VALUES
                (:user_id, :symbol, :name, :shares, :price, :total);
            """,
            user_id=session["user_id"],
            symbol=quoted_data["symbol"],
            name=quoted_data["name"],
            shares=int(request.form.get("shares")),
            price=quoted_data["price"],
            total=(quoted_data["price"] * int(request.form.get("shares")))
        )
        if purchase is None:
            return apology("Purchase could not be completed", 403)

        # Update cash in user
        user = db.execute(
            """
            UPDATE users
            SET cash=:cash
            WHERE id=:user_id;
            """,
            cash=(user[0]["cash"]-(quoted_data["price"])*int(request.form.get("shares"))),
            user_id=session["user_id"]
        )

        flash("Bought!")
        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        quoted_data = lookup(request.form.get("symbol"))
        return render_template("quoted.html", quote=quoted_data)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forger any user_id
    session.clear()

    # User reached the route via a POST request (form submission)
    if request.method == "POST":
        
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("provide confirmation password", 403)

        # Ensure passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords don't match", 403)
        
        # Query database for username and return if username alreadu exists
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        if len(rows) != 0:
            return apology("Username already exists")

        execute = db.execute(
            "INSERT INTO users (username, hash) VALUES (:username, :hash)",
            username=request.form.get("username"),
            hash=generate_password_hash(
                request.form.get("password"),
                method="pbkdf2:sha256",
                salt_length=8
            )
        )

        print(execute)

        if execute is not None:
            # Remember which user has logged in
            session["user_id"] = execute

            flash("Registered")

            # Redirect user to home page
            return redirect("/")
        else:
            return apology("Something went wrong", 500)

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
