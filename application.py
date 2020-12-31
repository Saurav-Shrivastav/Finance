import os
from datetime import datetime

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
    stocks = db.execute(
        "SELECT * FROM stocks WHERE user_id = :id",
        id=session["user_id"]
    )
    curr_prices = []
    total_prices = []
    for stock in stocks:
        quoted_data = lookup(stock["symbol"])
        curr_prices.append(quoted_data["price"])
        total_prices.append(quoted_data["price"] * stock["shares"])
    total_stocks_cash = sum(total_prices) + user[0]["cash"]
    return render_template(
        "portfolio.html",
        cash=user[0]["cash"],
        stocks_prices=zip(stocks, curr_prices, total_prices),
        total_stocks_cash=total_stocks_cash,
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

        stock_ea = db.execute(
            "SELECT * FROM stocks WHERE symbol = :symbol AND user_id = :id",
            symbol=quoted_data["symbol"],
            id=session["user_id"]
        )

        # Add a purchase
        purchase = db.execute(
                """
                    INSERT INTO purchases (user_id, symbol, name, shares, price, total, date)
                    VALUES
                    (:user_id, :symbol, :name, :shares, :price, :total, :date);
                """,
                user_id=session["user_id"],
                symbol=quoted_data["symbol"],
                name=quoted_data["name"],
                shares=int(request.form.get("shares")),
                price=quoted_data["price"],
                total=(quoted_data["price"] * int(request.form.get("shares"))),
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        if purchase is None:
                return apology("Purchase could not be completed", 403)

        if len(stock_ea) == 0:
            stock = db.execute(
                """
                INSERT INTO stocks (user_id, symbol, name, shares)
                VALUES
                (:user_id, :symbol, :name, :shares);
                """,
                user_id=session["user_id"],
                symbol=quoted_data["symbol"],
                name=quoted_data["name"],
                shares=int(request.form.get("shares")),
            )
        else: 
            stock = db.execute(
                """
                UPDATE stocks
                SET shares = :shares
                where user_id = :user_id AND symbol = :symbol;
                """,
                shares=stock_ea[0]["shares"] + int(request.form.get("shares")),
                user_id=session["user_id"],
                symbol=quoted_data["symbol"],
            )

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
    transactions = db.execute(
        """
        SELECT * FROM purchases
        WHERE user_id = :user_id;
        """,
        user_id=session["user_id"]
    )
    return render_template(
        "history.html",
        transactions=transactions,
    )


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
        if quoted_data is None:
            return apology("Invalid symbol", 403)
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

        if execute is not None:
            # Remember which user has logged in
            session["user_id"] = execute

            flash("Registered")

            # Redirect user to home page
            return redirect("/")
        else:
            return apology("Something went wrong", 500)

    return render_template("register.html")


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password"""
    
    if request.method == "POST":
        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE id = :user_id",
            user_id=session["user_id"]
        )
        
        print(rows, request.form.get('curr_password'))

        # Ensure current password is correct
        if not check_password_hash(rows[0]["hash"], request.form.get("curr_password")):
            return apology("invalid current password", 403)     

        # Ensure passwords match
        elif request.form.get("new_password") != request.form.get("confirmation"):
            return apology("New Passwords don't match", 403)   

        execute = db.execute(
            """
            UPDATE users 
            SET hash = :hash
            WHERE id = :user_id;
            """,
            user_id=session["user_id"],
            hash=generate_password_hash(
                request.form.get("new_password"),
                method="pbkdf2:sha256",
                salt_length=8
            )
        )

        session.clear()

        return redirect("/")

    return render_template(
        "change_password.html"
    )


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute(
        "SELECT * FROM stocks WHERE user_id = :id",
        id=session["user_id"]
    )
    
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 403)

        # Ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide the number of shares", 403)

        if int(request.form.get('shares')) <= 0:
            return apology("must provide a positive number of shares", 403)

        quoted_data = lookup(request.form.get("symbol"))
        if quoted_data is None:
            return apology("Invalid symbol", 403)

        stock = db.execute(
            """
            SELECT * 
            FROM stocks 
            WHERE user_id = :id AND symbol = :symbol
            """,
            id=session["user_id"],
            symbol=request.form.get('symbol')
        )

        if stock is None:
            return apology("You don't own any shares of the given stock", 403)

        if stock[0]["shares"] < int(request.form.get("shares")):
            return apology("You don't own enough shares", 403)

        # Add a purchase
        purchase = db.execute(
                """
                    INSERT INTO purchases (user_id, symbol, name, shares, price, total, date)
                    VALUES
                    (:user_id, :symbol, :name, :shares, :price, :total, :date);
                """,
                user_id=session["user_id"],
                symbol=quoted_data["symbol"],
                name=quoted_data["name"],
                shares=-(int(request.form.get("shares"))),
                price=quoted_data["price"],
                total=(quoted_data["price"] * int(request.form.get("shares"))),
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        
        if stock[0]["shares"] == int(request.form.get("shares")):
            stock = db.execute(
                """
                DELETE 
                FROM stocks 
                WHERE user_id = :id AND symbol = :symbol;
                """,
                id=session["user_id"],
                symbol=request.form.get("symbol")
            )
        else:
            updated_stock = db.execute(
                """
                UPDATE stocks
                SET shares = :shares
                WHERE user_id = :id AND symbol = :symbol;
                """,
                shares=(stock[0]["shares"] - int(request.form.get("shares"))),
                id=session["user_id"],
                symbol=request.form.get("symbol")
            )

        # Update cash in user
        user = db.execute(
            "SELECT * FROM users WHERE id = :id",
            id=session["user_id"]
        )
        user = db.execute(
            """
            UPDATE users
            SET cash=:cash
            WHERE id=:user_id;
            """,
            cash=(user[0]["cash"]+(quoted_data["price"])*int(request.form.get("shares"))),
            user_id=session["user_id"]
        )

        flash("Sold!")
        return redirect("/")


    return render_template(
        "sell.html",
        stocks=stocks
    )


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
