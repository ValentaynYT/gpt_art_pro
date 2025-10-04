from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import os
import hashlib
import sqlalchemy as sa

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-123'

# Инициализируем SQLAlchemy
db = SQLAlchemy()
db.init_app(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    products = db.relationship('Product', backref='owner', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qr_content = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def decode_qr_code(file):
    """Заглушка для QR-декодера"""
    class DecodedObject:
        def __init__(self, data):
            self.data = data.encode('utf-8')
            self.type = 'QRCODE'
    
    filename = file.filename if file else "test"
    filename_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    test_content = f"QR_Content_{filename_hash}"
    return [DecodedObject(test_content)]

@app.route("/upload", methods=['POST'])
def upload():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    file = request.files['file']
    if file and file.filename:
        decoded_objects = decode_qr_code(file)
        if decoded_objects:
            qr_content = decoded_objects[0].data.decode('utf-8')
            user = User.query.filter_by(email=session['user_email']).first()
            new_product = Product(qr_content=qr_content, user_id=user.id)
            db.session.add(new_product)
            db.session.commit()
            flash('Товар успешно добавлен! (тестовый режим)', 'success')
        else:
            flash('Не удалось декодировать QR-код.', 'warning')
    return redirect(url_for('second'))

@app.route("/second")
def second():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    products = user.products
    return render_template("second.html", products=products)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/third")
def third():
    return render_template("third.html")

@app.route("/four")
def four():
    return render_template("four.html")

@app.route("/gg")
def gg():
    return render_template("gg.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session['user_email'] = user.email
            flash('Вход успешен!', 'success')
            return redirect(url_for('gg'))
        else:
            flash('Неверный email или пароль!', 'danger')
    return render_template("login.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password1 = request.form['password1']
        password2 = request.form['password2']
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Пользователь с таким email уже существует!', 'danger')
        elif password1 != password2:
            flash('Пароли не совпадают!', 'danger')
        else:
            new_user = User(email=email, password=password1)
            db.session.add(new_user)
            db.session.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('gg'))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop('user_email', None)
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('login'))

@app.route('/add_shelf', methods=['POST'])
def add_shelf():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    name = request.form['name']
    user = User.query.filter_by(email=session['user_email']).first()
    new_shelf = Product(qr_content=name, user_id=user.id)
    db.session.add(new_shelf)
    db.session.commit()
    flash('Полка успешно добавлена!', 'success')
    return redirect(url_for('second'))

@app.route('/remove_shelf/<int:shelf_id>', methods=['POST'])
def remove_shelf(shelf_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    shelf = Product.query.get(shelf_id)
    if shelf:
        db.session.delete(shelf)
        db.session.commit()
        flash('Полка успешно удалена!', 'success')
    return redirect(url_for('second'))

@app.route('/remove_all_shelves', methods=['POST'])
def remove_all_shelves():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    Product.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    flash('Все полки успешно удалены!', 'success')
    return redirect(url_for('second'))

@app.route('/all_shelves')
def all_shelves():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    shelves = Product.query.filter_by(user_id=user.id).all()
    return render_template('all_shelves.html', shelves=shelves, total_products=len(shelves))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
