# Flight Reservation System - Single-file Flask App
# Save as app.py and run: python app.py
# Requirements: Flask (pip install flask)

from flask import Flask, request, redirect, url_for, render_template, flash
import sqlite3
from datetime import datetime, timedelta
import os
from jinja2 import DictLoader

DB_PATH = 'flights.db'

app = Flask(__name__)
app.secret_key = os.environ.get('FRS_SECRET', 'replace-with-a-secure-random-key')

# --- Database helpers ---

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # create DB file and tables if not present
    if os.path.exists(DB_PATH):
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE Flights(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_no TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            dep_time TEXT NOT NULL,
            arr_time TEXT NOT NULL,
            total_seats INTEGER NOT NULL,
            base_fare REAL NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE Passengers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            passport_no TEXT,
            contact TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE Bookings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            passenger_id INTEGER NOT NULL,
            flight_id INTEGER NOT NULL,
            seat_no TEXT NOT NULL,
            seat_class TEXT NOT NULL,
            fare REAL NOT NULL,
            booking_date TEXT NOT NULL,
            FOREIGN KEY(passenger_id) REFERENCES Passengers(id),
            FOREIGN KEY(flight_id) REFERENCES Flights(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Templates as strings (keeps single file) ---
base_tpl = '''
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <title>Flight Reservation System</title>
  </head>
  <body>
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
    <a class="navbar-brand" href="{{ url_for('index') }}">Flight System</a>
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav mr-auto">
        <li class="nav-item"><a class="nav-link" href="{{ url_for('list_flights') }}">Flights</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('add_flight') }}">Add Flight</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('view_bookings') }}">Bookings</a></li>
      </ul>
    </div>
  </nav>
  <div class="container mt-4">
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for m in messages %}
          <div class="alert alert-info">{{ m }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </div>
  </body>
</html>
'''

index_tpl = '''
{% extends 'base.html' %}
{% block content %}
  <div class="jumbotron">
    <h1 class="display-5">Welcome to the Flight Reservation System</h1>
    <p class="lead">Search flights, book seats, and manage reservations.</p>
    <hr class="my-4">
    <a class="btn btn-primary btn-lg" href="{{ url_for('list_flights') }}" role="button">View Flights</a>
  </div>
{% endblock %}
'''

list_flights_tpl = '''
{% extends 'base.html' %}
{% block content %}
  <h2>Available Flights</h2>
  <form method="get" class="form-inline mb-3">
    <input class="form-control mr-2" type="text" name="origin" placeholder="Origin" value="{{ request.args.get('origin','') }}">
    <input class="form-control mr-2" type="text" name="destination" placeholder="Destination" value="{{ request.args.get('destination','') }}">
    <input class="form-control mr-2" type="date" name="date" value="{{ request.args.get('date','') }}">
    <button class="btn btn-outline-primary">Search</button>
    <a class="btn btn-link ml-2" href="{{ url_for('list_flights') }}">Clear</a>
  </form>
  {% if flights %}
  <table class="table table-bordered">
    <thead>
      <tr>
        <th>#</th><th>Flight No</th><th>Airline</th><th>Route</th><th>Departure</th><th>Arrival</th><th>Seats Left</th><th>Base Fare</th><th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for f in flights %}
      <tr>
        <td>{{ f.id }}</td>
        <td>{{ f.flight_no }}</td>
        <td>{{ airline_name(f.flight_no) }}</td>
        <td>{{ f.origin }} -> {{ f.destination }}</td>
        <td>{{ f.dep_time }}</td>
        <td>{{ f.arr_time }}</td>
        <td>{{ seats_left[f.id] }}</td>
        <td>₹{{ '%.2f'|format(f.base_fare) }}</td>
        <td>
          <a class="btn btn-sm btn-success" href="{{ url_for('book_flight', flight_id=f.id) }}">Book</a>
          <a class="btn btn-sm btn-secondary" href="{{ url_for('view_flight', flight_id=f.id) }}">Details</a>
          <a class="btn btn-sm btn-danger" href="{{ url_for('delete_flight', flight_id=f.id) }}" onclick="return confirm('Delete this flight? This will also cancel all associated bookings!')">Delete</a>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
    <p>No flights found.</p>
  {% endif %}
{% endblock %}
'''

add_flight_tpl = '''
{% extends 'base.html' %}
{% block content %}
  <h2>Add Flight</h2>
  <form method="post">
    <div class="form-row">
      <div class="form-group col-md-3"><label>Flight No</label><input class="form-control" name="flight_no" required></div>
      <div class="form-group col-md-3"><label>Origin</label><input class="form-control" name="origin" required></div>
      <div class="form-group col-md-3"><label>Destination</label><input class="form-control" name="destination" required></div>
      <div class="form-group col-md-3"><label>Total Seats</label><input type="number" min="1" class="form-control" name="total_seats" required></div>
    </div>
    <div class="form-row">
      <div class="form-group col-md-4"><label>Departure (YYYY-MM-DD HH:MM)</label><input class="form-control" name="dep_time" placeholder="2025-09-20 14:30" required></div>
      <div class="form-group col-md-4"><label>Arrival (YYYY-MM-DD HH:MM)</label><input class="form-control" name="arr_time" placeholder="2025-09-20 16:50" required></div>
      <div class="form-group col-md-4"><label>Base Fare (₹)</label><input type="number" step="0.01" class="form-control" name="base_fare" required></div>
    </div>
    <button class="btn btn-primary">Add Flight</button>
  </form>
{% endblock %}
'''

flight_details_tpl = '''
{% extends 'base.html' %}
{% block content %}
  <h2>Flight Details - {{ flight.flight_no }} ({{ airline_name(flight.flight_no) }})</h2>
  <ul class="list-group mb-3">
    <li class="list-group-item"><strong>Airline:</strong> {{ airline_name(flight.flight_no) }}</li>
    <li class="list-group-item"><strong>Route:</strong> {{ flight.origin }} → {{ flight.destination }}</li>
    <li class="list-group-item"><strong>Departure:</strong> {{ flight.dep_time }}</li>
    <li class="list-group-item"><strong>Arrival:</strong> {{ flight.arr_time }}</li>
    <li class="list-group-item"><strong>Total Seats:</strong> {{ flight.total_seats }}</li>
    <li class="list-group-item"><strong>Seats Left:</strong> {{ seats_left }}</li>
    <li class="list-group-item"><strong>Base Fare:</strong> ₹{{ '%.2f'|format(flight.base_fare) }}</li>
  </ul>
  <a class="btn btn-success" href="{{ url_for('book_flight', flight_id=flight.id) }}">Book this Flight</a>
  <a class="btn btn-danger" href="{{ url_for('delete_flight', flight_id=flight.id) }}" onclick="return confirm('Delete this flight? This will also cancel all associated bookings!')">Delete Flight</a>
  <a class="btn btn-secondary" href="{{ url_for('list_flights') }}">Back</a>
{% endblock %}
'''

book_tpl = '''
{% extends 'base.html' %}
{% block content %}
  <h2>Book Flight - {{ flight.flight_no }} ({{ airline_name(flight.flight_no) }})</h2>
  <p><strong>Route:</strong> {{ flight.origin }} → {{ flight.destination }} | <strong>Departure:</strong> {{ flight.dep_time }}</p>
  <p><strong>Seats Left:</strong> {{ seats_left }}</p>

  {% if seats_left == 0 %}
    <div class="alert alert-danger">No seats available.</div>
  {% else %}
  <form method="post">
    <h5>Passenger Info</h5>
    <div class="form-row">
      <div class="form-group col-md-4"><input class="form-control" name="name" placeholder="Full Name" required></div>
      <div class="form-group col-md-2"><input class="form-control" type="number" name="age" placeholder="Age"></div>
      <div class="form-group col-md-2"><select class="form-control" name="gender"><option></option><option>Male</option><option>Female</option><option>Other</option></select></div>
      <div class="form-group col-md-4"><input class="form-control" name="passport_no" placeholder="Passport No / ID"></div>
    </div>
    <div class="form-row">
      <div class="form-group col-md-4"><input class="form-control" name="contact" placeholder="Contact (phone/email)"></div>
      <div class="form-group col-md-3">
        <label>Seat Class</label>
        <select class="form-control" name="seat_class">
          <option value="Economy">Economy</option>
          <option value="Business">Business</option>
        </select>
      </div>
      <div class="form-group col-md-3">
        <label>Seat No (example A1)</label>
        <input class="form-control" name="seat_no" placeholder="e.g. A1" required>
      </div>
    </div>
    <button class="btn btn-primary">Confirm Booking</button>
  </form>
  {% endif %}
{% endblock %}
'''

bookings_tpl = '''
{% extends 'base.html' %}
{% block content %}
  <h2>All Bookings</h2>
  {% if bookings %}
  <table class="table table-sm table-bordered">
    <thead>
      <tr><th>ID</th><th>Passenger</th><th>Flight</th><th>Seat</th><th>Class</th><th>Fare</th><th>Booking Date</th><th>Action</th></tr>
    </thead>
    <tbody>
      {% for b in bookings %}
      <tr>
        <td>{{ b.id }}</td>
        <td>{{ b.pname }}</td>
  <td>{{ airline_name(b.fno) }} - {{ b.fno }} ({{ b.route }})</td>
        <td>{{ b.seat_no }}</td>
        <td>{{ b.seat_class }}</td>
        <td>₹{{ '%.2f'|format(b.fare) }}</td>
        <td>{{ b.booking_date }}</td>
        <td><a class="btn btn-sm btn-danger" href="{{ url_for('cancel_booking', booking_id=b.id) }}" onclick="return confirm('Cancel booking?')">Cancel</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
    <p>No bookings yet.</p>
  {% endif %}
{% endblock %}
'''

# Register templates using DictLoader (more reliable than mutating jinja_loader.mapping)
app.jinja_loader = DictLoader({
    'base.html': base_tpl,
    'index.html': index_tpl,
    'list_flights.html': list_flights_tpl,
    'add_flight.html': add_flight_tpl,
    'flight_details.html': flight_details_tpl,
    'book.html': book_tpl,
    'bookings.html': bookings_tpl,
})

# --- Utility functions ---

def seats_left_for_flight(conn, flight_id):
    total_row = conn.execute('SELECT total_seats FROM Flights WHERE id=?', (flight_id,)).fetchone()
    if not total_row:
        return 0
    total = total_row['total_seats']
    booked = conn.execute('SELECT COUNT(*) as c FROM Bookings WHERE flight_id=?', (flight_id,)).fetchone()['c']
    return total - booked


# --- Airline helper ---
def airline_name_from_flight_no(flight_no):
  """Return a human-friendly airline name parsed from flight_no.

  This keeps the file and DB schema unchanged while showing an airline name
  in the UI (e.g. 'AI-101' -> 'Air India').
  """
  if not flight_no:
    return 'Unknown Airline'
  prefix = str(flight_no).split('-')[0].upper()
  mapping = {
    'AI': 'Air India',
    '6E': 'IndiGo',
    'SG': 'SpiceJet',
    'UK': 'Vistara',
    'IX': 'Air India Express',
    'G8': 'GoFirst',
  }
  return mapping.get(prefix, 'Unknown Airline')

# make available inside Jinja templates
app.jinja_env.globals['airline_name'] = airline_name_from_flight_no


def calculate_fare(base_fare, seat_class, dep_time_str, booking_time=None):
    mult = 1.0 if (seat_class or '').lower() == 'economy' else 1.5
    try:
        base_fare = float(base_fare)
    except Exception:
        base_fare = 0.0
    fare = base_fare * mult
    if booking_time is None:
        booking_time = datetime.now()
    dep_time = None
    try:
        dep_time = datetime.strptime(dep_time_str, '%Y-%m-%d %H:%M')
    except Exception:
        # accept a yyyy-mm-dd date without time
        try:
            dep_time = datetime.strptime(dep_time_str, '%Y-%m-%d')
        except Exception:
            dep_time = None
    if dep_time and (dep_time - booking_time) <= timedelta(hours=48):
        fare *= 1.2
    fare *= 1.05  # GST
    return round(fare, 2)

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/flights')
def list_flights():
    origin = request.args.get('origin', '').strip()
    destination = request.args.get('destination', '').strip()
    date = request.args.get('date', '').strip()
    conn = get_db_connection()
    q = 'SELECT * FROM Flights'
    params = []
    filters = []
    if origin:
        filters.append("origin LIKE ?")
        params.append(f"%{origin}%")
    if destination:
        filters.append("destination LIKE ?")
        params.append(f"%{destination}%")
    if date:
        filters.append("dep_time LIKE ?")
        params.append(f"{date}%")
    if filters:
        q += ' WHERE ' + ' AND '.join(filters)
    flights = conn.execute(q, params).fetchall()
    seats_left = {f['id']: seats_left_for_flight(conn, f['id']) for f in flights}
    conn.close()
    return render_template('list_flights.html', flights=flights, seats_left=seats_left)

@app.route('/flights/add', methods=['GET','POST'])
def add_flight():
    if request.method == 'POST':
        try:
            flight_no = request.form['flight_no'].strip()
            origin = request.form['origin'].strip()
            destination = request.form['destination'].strip()
            dep_time = request.form['dep_time'].strip()
            arr_time = request.form['arr_time'].strip()
            total_seats = int(request.form['total_seats'])
            base_fare = float(request.form['base_fare'])
            # validate dep_time format
            try:
                datetime.strptime(dep_time, '%Y-%m-%d %H:%M')
            except Exception:
                flash('Departure time format should be YYYY-MM-DD HH:MM')
                return redirect(url_for('add_flight'))
            conn = get_db_connection()
            conn.execute('INSERT INTO Flights(flight_no, origin, destination, dep_time, arr_time, total_seats, base_fare) VALUES (?,?,?,?,?,?,?)',
                         (flight_no, origin, destination, dep_time, arr_time, total_seats, base_fare))
            conn.commit()
            conn.close()
            flash('Flight added successfully')
            return redirect(url_for('list_flights'))
        except ValueError:
            flash('Please enter valid numeric values for seats and fare')
            return redirect(url_for('add_flight'))
    return render_template('add_flight.html')

@app.route('/flight/<int:flight_id>')
def view_flight(flight_id):
    conn = get_db_connection()
    flight = conn.execute('SELECT * FROM Flights WHERE id=?', (flight_id,)).fetchone()
    if not flight:
        conn.close()
        flash('Flight not found')
        return redirect(url_for('list_flights'))
    seats_left = seats_left_for_flight(conn, flight_id)
    conn.close()
    return render_template('flight_details.html', flight=flight, seats_left=seats_left)

@app.route('/flight/<int:flight_id>/delete')
def delete_flight(flight_id):
    conn = get_db_connection()
    flight = conn.execute('SELECT * FROM Flights WHERE id=?', (flight_id,)).fetchone()
    if not flight:
        conn.close()
        flash('Flight not found')
        return redirect(url_for('list_flights'))
    
    # Check if there are any bookings for this flight
    bookings_count = conn.execute('SELECT COUNT(*) as c FROM Bookings WHERE flight_id=?', (flight_id,)).fetchone()['c']
    
    if bookings_count > 0:
        # Delete associated bookings first (due to foreign key constraint)
        conn.execute('DELETE FROM Bookings WHERE flight_id=?', (flight_id,))
        flash(f'Flight {flight["flight_no"]} and {bookings_count} associated booking(s) have been deleted')
    else:
        flash(f'Flight {flight["flight_no"]} has been deleted')
    
    # Delete the flight
    conn.execute('DELETE FROM Flights WHERE id=?', (flight_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('list_flights'))

@app.route('/flight/<int:flight_id>/book', methods=['GET','POST'])
def book_flight(flight_id):
    conn = get_db_connection()
    flight = conn.execute('SELECT * FROM Flights WHERE id=?', (flight_id,)).fetchone()
    if not flight:
        conn.close()
        flash('Flight not found')
        return redirect(url_for('list_flights'))
    seats_left = seats_left_for_flight(conn, flight_id)
    if request.method == 'POST':
        if seats_left <= 0:
            flash('No seats available')
            conn.close()
            return redirect(url_for('list_flights'))
        name = request.form['name'].strip()
        age = request.form.get('age')
        gender = request.form.get('gender')
        passport_no = request.form.get('passport_no')
        contact = request.form.get('contact')
        seat_class = request.form.get('seat_class')
        seat_no = request.form.get('seat_no').strip()
        if not seat_no:
            flash('Seat number is required')
            conn.close()
            return redirect(url_for('book_flight', flight_id=flight_id))
        # ensure seat_no isn't already taken for this flight
        existing = conn.execute('SELECT * FROM Bookings WHERE flight_id=? AND seat_no=?', (flight_id, seat_no)).fetchone()
        if existing:
            flash('Seat already booked. Choose another seat_no')
            conn.close()
            return redirect(url_for('book_flight', flight_id=flight_id))
        # create passenger
        cur = conn.cursor()
        try:
            age_val = int(age) if age else None
        except Exception:
            age_val = None
        cur.execute('INSERT INTO Passengers(name, age, gender, passport_no, contact) VALUES (?,?,?,?,?)',
                    (name, age_val, gender, passport_no, contact))
        pid = cur.lastrowid
        # calculate fare
        fare = calculate_fare(flight['base_fare'], seat_class, flight['dep_time'])
        booking_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        cur.execute('INSERT INTO Bookings(passenger_id, flight_id, seat_no, seat_class, fare, booking_date) VALUES (?,?,?,?,?,?)',
                    (pid, flight_id, seat_no, seat_class, fare, booking_date))
        conn.commit()
        conn.close()
        flash(f'Booking confirmed. Fare: ₹{fare:.2f}')
        return redirect(url_for('view_bookings'))
    conn.close()
    return render_template('book.html', flight=flight, seats_left=seats_left)

@app.route('/bookings')
def view_bookings():
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT B.*, P.name as pname, F.flight_no as fno, F.origin || '->' || F.destination as route
        FROM Bookings B
        JOIN Passengers P ON P.id = B.passenger_id
        JOIN Flights F ON F.id = B.flight_id
        ORDER BY B.id DESC
    ''').fetchall()
    conn.close()
    bookings = rows
    return render_template('bookings.html', bookings=bookings)

@app.route('/booking/<int:booking_id>/cancel')
def cancel_booking(booking_id):
    conn = get_db_connection()
    b = conn.execute('SELECT * FROM Bookings WHERE id=?', (booking_id,)).fetchone()
    if not b:
        conn.close()
        flash('Booking not found')
        return redirect(url_for('view_bookings'))
    conn.execute('DELETE FROM Bookings WHERE id=?', (booking_id,))
    conn.commit()
    conn.close()
    flash('Booking cancelled and seat released')
    return redirect(url_for('view_bookings'))

# --- Run server ---
if __name__ == '__main__':
    # create some sample data if DB was just created
    conn = get_db_connection()
    c = conn.cursor()
    count = c.execute('SELECT COUNT(*) as c FROM Flights').fetchone()['c']
    if count == 0:
        now = datetime.now()
        sample = [
            ('AI-101','Mumbai','Delhi', (now+timedelta(days=1)).strftime('%Y-%m-%d 09:30'), (now+timedelta(days=1)).strftime('%Y-%m-%d 11:30'), 120, 3500.0),
            ('AI-202','Bengaluru','Hyderabad', (now+timedelta(days=2)).strftime('%Y-%m-%d 14:00'), (now+timedelta(days=2)).strftime('%Y-%m-%d 15:15'), 80, 2500.0),
            ('AI-303','Kolkata','Chennai', (now+timedelta(days=3)).strftime('%Y-%m-%d 20:15'), (now+timedelta(days=3)).strftime('%Y-%m-%d 22:45'), 150, 4200.0),
        ]
        c.executemany('INSERT INTO Flights(flight_no, origin, destination, dep_time, arr_time, total_seats, base_fare) VALUES (?,?,?,?,?,?,?)', sample)
        conn.commit()
    conn.close()
    app.run(debug=True)