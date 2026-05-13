from flask import Flask, render_template, request, redirect, session, flash, Response
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
import random
import csv
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

app.config['SESSION_PERMANENT'] = False

# DATABASE CREATION
def init_db():

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Customers Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        mobile TEXT,
        amount REAL,
        eligible TEXT,
        date TEXT
    )
    ''')

    # Settings Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        min_amount REAL,
        draw_type TEXT,
        gift_name TEXT
    )
    ''')

    # Admin Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    ''')

    # Winner Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS winner(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        winner_name TEXT,
        gift TEXT,
        draw_type TEXT,
        date TEXT
    )
    ''')

    # Default Settings
    cur.execute("SELECT * FROM settings")

    if not cur.fetchone():

        cur.execute(
            '''
            INSERT INTO settings
            (min_amount,draw_type,gift_name)
            VALUES(?,?,?)
            ''',
            (300, "Weekly", "Bluetooth Speaker")
        )

    # Default Admin
    cur.execute("SELECT * FROM admin")

    if not cur.fetchone():

        username = os.getenv("ADMIN_USERNAME")

        password = generate_password_hash(
            os.getenv("ADMIN_PASSWORD")
        )

        cur.execute(
            "INSERT INTO admin(username,password) VALUES(?,?)",
            (username,password)
        )

    conn.commit()
    conn.close()

# Initialize database
init_db()

@app.route('/')
def home():

    return render_template('winner.html')
# ADMIN LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    
    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM admin WHERE username=?",
            (username,)
        )

        admin = cur.fetchone()

        conn.close()

        if admin and check_password_hash(admin[2], password):

            session['admin'] = username

            return redirect('/dashboard')

        else:

            flash("Invalid Username or Password")

            return redirect('/login')

    return render_template('login.html')

# DASHBOARD
@app.route('/dashboard')
def dashboard():

    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Total customers
    cur.execute("SELECT COUNT(*) FROM customers")

    total_customers = cur.fetchone()[0]

    # Eligible customers
    cur.execute(
        "SELECT COUNT(*) FROM customers WHERE eligible='Yes'"
    )

    eligible_customers = cur.fetchone()[0]

    # Settings
    cur.execute("SELECT * FROM settings LIMIT 1")

    settings = cur.fetchone()

    conn.close()

    return render_template(
        'dashboard.html',
        total_customers=total_customers,
        eligible_customers=eligible_customers,
        settings=settings
    )

# CUSTOMER REGISTRATION PAGE (ADMIN ONLY)
@app.route('/register_customer')
def register_customer():

    if 'admin' not in session:
        return redirect('/login')

    return render_template('index.html')

# CUSTOMER SUBMISSION
@app.route('/submit', methods=['POST'])
def submit():

    if 'admin' not in session:
        return redirect('/login')

    name = request.form['name']
    mobile = request.form['mobile']
    amount = float(request.form['amount'])

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Check duplicate mobile number
    cur.execute(
        "SELECT * FROM customers WHERE mobile=?",
        (mobile,)
    )

    existing_customer = cur.fetchone()

    if existing_customer:

        conn.close()

        flash("Mobile number already registered!")

        return redirect('/register_customer')

    # Get minimum amount
    cur.execute("SELECT min_amount FROM settings LIMIT 1")

    min_amount = cur.fetchone()[0]

    # Eligibility check
    eligible = "Yes"

    if amount < min_amount:
        eligible = "No"

    # Save customer
    cur.execute('''
    INSERT INTO customers
    (name,mobile,amount,eligible,date)
    VALUES(?,?,?,?,?)
    ''',
    (
        name,
        mobile,
        amount,
        eligible,
        datetime.now().strftime("%Y-%m-%d")
    ))

    conn.commit()
    conn.close()

    if eligible == "Yes":
        flash("Customer Registered Successfully!")
    else:
        flash("Customer Registered But Not Eligible")

    return redirect('/register_customer')

# UPDATE SETTINGS
@app.route('/update_settings', methods=['POST'])
def update_settings():

    if 'admin' not in session:
        return redirect('/login')

    min_amount = request.form['min_amount']
    draw_type = request.form['draw_type']
    gift_name = request.form['gift_name']

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute('''
    UPDATE settings
    SET min_amount=?,
        draw_type=?,
        gift_name=?
    WHERE id=1
    ''',
    (
        min_amount,
        draw_type,
        gift_name
    ))

    conn.commit()
    conn.close()

    flash("Settings Updated Successfully!")

    return redirect('/dashboard')

# SELECT WINNER MANUALLY
@app.route('/select_winner')
def select_winner():

    if 'admin' not in session:
        return redirect('/login')

    auto_select_winner()

    flash("Winner Selected Successfully!")

    return redirect('/winner')

# WINNER PAGE (PUBLIC)
@app.route('/winner')
def winner():

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM winner ORDER BY id DESC LIMIT 1"
    )

    data = cur.fetchone()

    conn.close()

    return render_template(
        'winner.html',
        data=data
    )

# VIEW CUSTOMERS
@app.route('/customers')
def customers():

    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM customers ORDER BY id DESC"
    )

    customer_data = cur.fetchall()

    conn.close()

    return render_template(
        'customers.html',
        customers=customer_data
    )

# SEARCH CUSTOMERS
@app.route('/search_customers', methods=['POST'])
def search_customers():

    if 'admin' not in session:
        return redirect('/login')

    keyword = request.form['keyword']

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute('''
    SELECT * FROM customers
    WHERE name LIKE ?
    OR mobile LIKE ?
    ORDER BY id DESC
    ''',
    (
        '%' + keyword + '%',
        '%' + keyword + '%'
    ))

    customer_data = cur.fetchall()

    conn.close()

    return render_template(
        'customers.html',
        customers=customer_data
    )

# EXPORT CUSTOMERS CSV
@app.route('/export_customers')
def export_customers():

    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM customers")

    customers = cur.fetchall()

    conn.close()

    def generate():

        header = [
            'ID',
            'Name',
            'Mobile',
            'Amount',
            'Eligible',
            'Date'
        ]

        yield ','.join(header) + '\n'

        for customer in customers:

            row = [
                str(customer[0]),
                customer[1],
                customer[2],
                str(customer[3]),
                customer[4],
                customer[5]
            ]

            yield ','.join(row) + '\n'

    return Response(
        generate(),
        mimetype='text/csv',
        headers={
            'Content-Disposition':
            'attachment; filename=customers.csv'
        }
    )

# CHANGE PASSWORD
@app.route('/change_password', methods=['GET','POST'])
def change_password():

    if 'admin' not in session:
        return redirect('/login')

    if request.method == 'POST':

        old_password = request.form['old_password']
        new_password = request.form['new_password']

        conn = sqlite3.connect('database.db')
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM admin WHERE username=?",
            (session['admin'],)
        )

        admin = cur.fetchone()

        if admin and check_password_hash(admin[2], old_password):

            hashed_password = generate_password_hash(new_password)

            cur.execute(
                '''
                UPDATE admin
                SET password=?
                WHERE username=?
                ''',
                (
                    hashed_password,
                    session['admin']
                )
            )

            conn.commit()

            flash("Password Changed Successfully!")

        else:

            flash("Old Password Incorrect!")

        conn.close()

        return redirect('/dashboard')

    return render_template('change_password.html')

# DELETE CUSTOMER
@app.route('/delete_customer/<int:id>')
def delete_customer(id):

    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM customers WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    flash("Customer Deleted Successfully!")

    return redirect('/customers')

# AUTOMATIC WINNER SELECTION
def auto_select_winner():

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Get settings
    cur.execute("SELECT * FROM settings LIMIT 1")

    settings = cur.fetchone()

    if not settings:
        conn.close()
        return

    min_amount = settings[1]
    draw_type = settings[2]
    gift_name = settings[3]

    # Get eligible customers
    cur.execute('''
    SELECT * FROM customers
    WHERE amount >= ?
    ''',
    (min_amount,)
    )

    customers = cur.fetchall()

    if customers:

        winner = random.choice(customers)

        winner_name = winner[1]

        # Clear old winner
        cur.execute("DELETE FROM winner")

        # Save new winner
        cur.execute('''
        INSERT INTO winner
        (winner_name,gift,draw_type,date)
        VALUES(?,?,?,?)
        ''',
        (
            winner_name,
            gift_name,
            draw_type,
            datetime.now().strftime("%Y-%m-%d")
        ))

        conn.commit()

    conn.close()

# START SCHEDULER
scheduler = BackgroundScheduler()

# Automatic winner every 7 days
scheduler.add_job(
    auto_select_winner,
    'interval',
    days=7
)

scheduler.start()

# LOGOUT
@app.route('/logout')
def logout():

    session.pop('admin', None)

    flash("Logged Out Successfully!")

    return redirect('/login')

# RUN APPLICATION
if __name__ == '__main__':
    app.run(debug=True)