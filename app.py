from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configuration for file uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

DATABASE = 'database.db'

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    db = get_db()
    items = db.execute('SELECT items.*, users.username FROM items JOIN users ON items.user_id = users.id ORDER BY created_at DESC').fetchall()
    return render_template('index.html', items=items)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
            db.commit()
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or Email already taken.')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully.')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    db = get_db()
    # Fetch all items with image filename, so all users see identical list including images
    items = db.execute('SELECT items.*, users.username FROM items JOIN users ON items.user_id = users.id ORDER BY created_at DESC').fetchall()
    responses = db.execute('SELECT r.*, i.title FROM responses r JOIN items i ON r.item_id = i.id ORDER BY r.created_at DESC').fetchall()
    return render_template('dashboard.html', items=items, responses=responses)

@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        status = request.form['status']

        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename

        db = get_db()
        db.execute(
            'INSERT INTO items (title, description, status, user_id, image) VALUES (?, ?, ?, ?, ?)',
            (title, description, status, session['user_id'], image_filename)
        )
        db.commit()
        flash('Item added successfully.')
        return redirect(url_for('dashboard'))
    return render_template('add_item.html')

@app.route('/item/<int:item_id>', methods=['GET', 'POST'])
def item_detail(item_id):
    db = get_db()
    item = db.execute('SELECT items.*, users.username FROM items JOIN users ON items.user_id = users.id WHERE items.id = ?', (item_id,)).fetchone()
    responses = db.execute('SELECT r.*, u.username FROM responses r JOIN users u ON r.user_id = u.id WHERE r.item_id = ?', (item_id,)).fetchall()
    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Please log in to respond.')
            return redirect(url_for('login'))
        message = request.form['message']
        db.execute('INSERT INTO responses (item_id, user_id, message) VALUES (?, ?, ?)', (item_id, session['user_id'], message))
        db.commit()
        flash('Response sent to the item owner.')
        return redirect(url_for('item_detail', item_id=item_id))
    return render_template('item_detail.html', item=item, responses=responses)

@app.route('/search')
def search():
    q = request.args.get('q', '')
    db = get_db()
    items = db.execute('SELECT * FROM items WHERE title LIKE ? OR description LIKE ?', (f'%{q}%', f'%{q}%')).fetchall()
    return render_template('search.html', items=items, q=q)

if __name__ == '__main__':
    app.run(debug=True)
