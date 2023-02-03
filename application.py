import os
import settings

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Set API key
api_key = os.getenv("API_KEY")

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
###########
# NOTE: must be run in non-debugging mode or the db will run into a threading error
###########
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT symbol,SUM(shares) FROM portfolio WHERE user_id = (:id) GROUP BY symbol", id=session["user_id"])

    # Pop symbols that have 0 shares
    for i in range(0, len(rows)):
        if rows[i]["SUM(shares)"] == 0:
            rows.pop(i)

    # Obtain current prices and company names of symbols
    for item in rows:
        item["price"] = lookup(item["symbol"])["price"]
        item["name"] = lookup(item["symbol"])["name"]

    print(rows)

    # Obtain cash on hand
    cash_rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    cash = cash_rows[0]['cash']

    # Display a subtotal
    total = cash
    for item in rows:
        total += item["price"] * item["SUM(shares)"]

    return render_template("index.html", rows=rows, cash=cash, total=total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        symbol = request.form.get("symbol")

        # Check if shares valid
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("must provide valid shares")
        except ValueError:
            return apology("must provide valid shares")

        # Check if symbol was provided
        if not symbol:
            return apology("missing symbol")

        # Check if symbol is valid
        elif lookup(symbol) == None:
            return apology("invalid symbol")

        # All checks met
        else:
            # We have the data of the user's POST request (symbol, shares)
            symbol = symbol.upper()         # Change symbol to uppercase
            price = lookup(symbol)["price"] # Retrieve stock price (float)

            # Select how much cash the user has
            rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
            cash = rows[0]['cash']

            # Check if user does not have enough cash, return apology
            if shares * price > cash:
                return apology("not enough cash on hand")

            # Insert purchase data into the purchases table in db
            else:
                db.execute("INSERT INTO portfolio (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)", user_id=session["user_id"], symbol=symbol, shares=shares, price=price)

                # Update how much cash is on hand
                cash -= (shares * price)
                db.execute("UPDATE users SET cash = (:cash) WHERE id = (:id)", cash=cash, id=session["user_id"])

                # Redirect user
                return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM portfolio WHERE user_id = (:user_id) ORDER BY time", user_id=session["user_id"])

    print(rows)

    return render_template("history.html", rows=rows)


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

@app.route("/graph")
@login_required
def graph():
    """Display chart of portfolio"""
    rows = db.execute("SELECT symbol,SUM(shares) FROM portfolio WHERE user_id = (:id) GROUP BY symbol", id=session["user_id"])

    # Pop symbols that have 0 shares
    for i in range(0, len(rows)):
        if rows[i]["SUM(shares)"] == 0:
            rows.pop(i)

    # Obtain current prices and company names of symbols
    for item in rows:
        item["price"] = lookup(item["symbol"])["price"]
        item["name"] = lookup(item["symbol"])["name"]

    # Obtain cash on hand
    cash_rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    cash = cash_rows[0]['cash']

    # Obtain list of symbols (add cash)
    symbols = []
    for item in rows:
        symbols.append(item["symbol"])
    symbols.append("CASH")

    # Obtain list of totals (add cash)
    totals = []
    for item in rows:
        totals.append(item["price"] * item["SUM(shares)"])
    totals.append(cash)

    # Pass list of lists we will use for the Chart
    return render_template("graph.html", symbols=symbols, totals=totals)


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
    return render_template("quote.html")

@app.route("/quoted")
@login_required
def quoted():
    """Display quoted stock."""
    symbol = request.args.get("symbol")

    # Check if symbol was provided
    if not symbol:
        return apology("missing symbol")

    # Check if symbol is valid
    elif lookup(symbol) == None:
        return apology("invalid symbol")

    # All checks met
    else:
        # Display the stock's information at quoted.html
        stock = lookup(symbol)      # Stock dictionary
        print(stock)
        company = stock["name"]     # Company name
        price = usd(stock["price"]) # Stock price

        return render_template("quoted.html", company=company, price=price, symbol=symbol.upper())

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        # Get data posted from the form at /register
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        password_hash = generate_password_hash(password)

        # Check if username is already taken (check database)
        if len(db.execute("SELECT * FROM users WHERE username = (:username)", username=username)) > 0:
            return apology("username already taken")

        # Check if username is blank
        elif not username:
            return apology("missing username")

        # Check if password is blank
        elif not password:
            return apology("missing password")

        # Check if both passwords match
        elif password != confirmation:
            return apology("passwords don't match")

        # All checks met
        else:
            # Register the user
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :password_hash)", username=username, password_hash=password_hash)
            return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":

        # All symbols' current amount of shares held
        rows = db.execute("SELECT symbol,SUM(shares) FROM portfolio WHERE user_id = (:id) GROUP BY symbol", id=session["user_id"])

         # Pop symbols that have 0 shares
        for i in range(0, len(rows)):
            if rows[i]["SUM(shares)"] == 0:
                rows.pop(i)

        return render_template("sell.html", rows=rows)

    else:
        # Check if symbol is valid
        try:
            symbol = request.form.get("symbol").upper()
        except AttributeError:
            return apology("must provide valid symbol and shares")

        shares = request.form.get("shares")

        # Check if shares valid
        try:
            shares = int(request.form.get("shares"))
            if shares <= 0:
                return apology("must provide valid shares")
        except ValueError:
            return apology("must provide valid shares")

        # Check if the user owns that many shares to sell
        if shares > db.execute("""SELECT SUM(shares) FROM portfolio WHERE user_id = (:user_id) and symbol = (:symbol) GROUP BY symbol;""", user_id=session["user_id"], symbol=symbol)[0]["SUM(shares)"]:
            return apology("Not enough shares owned")

        else:
            # Retrieve stock price (float)
            price = lookup(symbol)["price"]

            db.execute("INSERT INTO portfolio (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)", user_id=session["user_id"], symbol=symbol, shares=(-1 * shares), price=price)

            # Select how much cash the user has
            rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
            cash = rows[0]['cash']

            # Update how much cash is on hand
            cash += (shares * price)
            db.execute("UPDATE users SET cash = (:cash) WHERE id = (:id)", cash=cash, id=session["user_id"])

            # Redirect user
            return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
