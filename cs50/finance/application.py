import os
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import sys

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
    user_id = session["user_id"]
    casht = db.execute("SELECT * FROM portfoliostocks WHERE user_id = :user_id AND symbol= :cash", user_id=user_id, cash="CASH")
    rows = db.execute("SELECT * FROM portfoliostocks WHERE user_id = :user_id", user_id=user_id)
    return render_template("index.html", rows=rows, casht=casht)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "GET":
        return render_template("buy.html")
    else:
        print('money  through', file=sys.stderr)
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        elif not request.form.get("shares"):
            return apology("must provide the number of shares you would like to buy", 403)
        symbol = request.form.get("symbol")

        val = lookup(symbol)
        numshares = float(request.form.get("shares"))

        cost = val["price"] * numshares
        user_id = session["user_id"]
        rows = db.execute("SELECT total FROM portfoliostocks WHERE user_id = :user_id AND symbol=:cash",user_id=user_id, cash="CASH")
        cash = float(rows[0]["total"])

        if cost > cash:
            return apology("You don't have enough money to make this purchase")
        else:
            money = cash-cost

            now = datetime.now()
            rows = db.execute("SELECT * FROM portfoliostocks WHERE user_id = :user_id AND symbol=:symbol",user_id=user_id, symbol=symbol)
            if len(rows) > 0:
                cshares = float(rows[0]["shares"])
                currenttotal = float(rows[0]["total"])
                newnumshares = cshares + numshares
                brandnewtotal = cost + currenttotal
                db.execute("UPDATE portfoliostocks set shares = :shares WHERE user_id = :user_id AND symbol=:symbol", shares=newnumshares, user_id=user_id, symbol=symbol)
                db.execute("UPDATE portfoliostocks set total = :total WHERE user_id = :user_id AND symbol=:symbol", total=brandnewtotal, user_id=user_id, symbol=symbol)
                db.execute("UPDATE portfoliostocks set total = :money WHERE user_id = :user_id AND symbol=:cash", money=money, user_id=user_id, cash="CASH")
                db.execute("INSERT INTO history(user_id, symbol, shares, price, transacted) VALUES (:user_id, :symbol, :shares, :price, :transacted)",
                user_id=user_id, symbol=symbol, shares=numshares, price=val["price"], transacted=now)
            else:
                db.execute("INSERT INTO portfoliostocks(user_id, symbol, name, shares, price, total) VALUES (:user_id, :symbol, :name, :shares, :price, :total)",
                user_id=user_id, symbol=symbol, name=val["name"], shares=numshares, price=val["price"], total=cost)
                db.execute("UPDATE portfoliostocks set total = :money WHERE user_id = :user_id AND symbol=:cash", money=money, user_id=user_id, cash="CASH")
                db.execute("INSERT INTO history(user_id, symbol, shares, price, transacted) VALUES (:user_id, :symbol, :shares, :price, :transacted)",
                user_id=user_id, symbol=symbol, shares=numshares, price=val["price"], transacted=now)
            return redirect("/")

@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    casht = db.execute("SELECT * FROM history WHERE user_id = :user_id AND symbol= :cash", user_id=user_id, cash="CASH")
    rows = db.execute("SELECT * FROM history WHERE user_id = :user_id", user_id=user_id)
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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 403)
        symbol = request.form.get("symbol")
        vals = lookup(symbol)
        if not vals:
            return apology("must provide valid symbol ", 403)
        else:
            return render_template("quoteResults.html", vals=vals)



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        elif not request.form.get("confirmPassword"):
            return apology("must confirm password", 403)
        elif request.form.get("password") != request.form.get("confirmPassword"):
            return apology("passwords do not match", 403)
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(rows) != 0:
            return apology("duplicate username", 403)
        else:
            username=request.form.get("username")
            password=request.form.get("password")
            pw_hash = generate_password_hash(password)

            ototal = 10000
            db.execute("INSERT INTO users(username, hash) VALUES (:username, :password)", username=username, password=pw_hash)


                    # Query database for username
            rows = db.execute("SELECT * FROM users WHERE username = :username",
                              username=request.form.get("username"))

            # Ensure username exists and password is correct
            if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
                return apology("invalid username and/or password", 403)

            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]
            user_id = rows[0]["id"]
            db.execute("INSERT INTO portfoliostocks(user_id, symbol, total) VALUES (:user_id, :symbol, :total)",user_id=user_id, symbol="CASH", total=ototal)
            # Redirect user to home page
            return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        user_id = session["user_id"]
        rows = db.execute("SELECT DISTINCT symbol FROM portfoliostocks WHERE user_id = :user_id", user_id=user_id)
        i=1
        return render_template("sell.html", rows=rows, i=i)
    else:
        if not request.form.get("shares"):
            return apology("must provide the number of shares of this symbol you would like to sell", 403)
        else:
            user_id=session["user_id"]
            symbol = request.form.get('symbol')
            rows = db.execute("SELECT * FROM portfoliostocks WHERE user_id = :user_id AND symbol = :symbol",
            user_id = user_id, symbol= symbol)
            totalnumshares = 0
            numsharesSell=float(request.form.get("shares"))
            for row in rows:
                number = float(row["shares"])
                totalnumshares=totalnumshares+number

            print(totalnumshares, file=sys.stderr)
            if totalnumshares < numsharesSell:
                return apology("you don't own enough shares to sell", 403)
            else:
                now = datetime.now()
                vals = lookup(symbol)
                currentprice = float(vals["price"])
                cost = currentprice*numsharesSell
                rows = db.execute("Select * from portfoliostocks WHERE user_id= :user_id AND symbol = :cash", user_id = user_id, cash="CASH")
                priortotal = rows[0]["total"]
                newtotal = priortotal+cost
                pups = db.execute("Select * from portfoliostocks WHERE user_id= :user_id AND symbol = :symbol", user_id = user_id, symbol=symbol)
                cnumshares = pups[0]["shares"]
                newnumshares = cnumshares-numsharesSell
                db.execute("UPDATE portfoliostocks set total = :money WHERE user_id = :user_id AND symbol=:cash", money=newtotal, user_id=user_id, cash="CASH")
                db.execute("UPDATE portfoliostocks set shares = :shares WHERE user_id = :user_id AND symbol=:symbol", shares=newnumshares, user_id=user_id, symbol=symbol)
                negative = numsharesSell * -1
                db.execute("INSERT INTO history(user_id, symbol, shares, price, transacted) VALUES (:user_id, :symbol, :shares, :price, :transacted)",
                user_id=user_id, symbol=symbol, shares=negative, price=currentprice, transacted=now)
                lolo = db.execute("Select * from portfoliostocks WHERE user_id= :user_id AND symbol = :symbol", user_id = user_id, symbol=symbol)
                poioi = lolo[0]["shares"]
                print(poioi, file=sys.stderr)
                if poioi == 0:
                    print("in if loop", file=sys.stderr)
                    db.execute("DELETE FROM portfoliostocks WHERE user_id= :user_id AND symbol = :symbol", user_id = user_id, symbol=symbol)

            return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
