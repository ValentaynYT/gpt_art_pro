from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from pyzbar.pyzbar import decode
from PIL import Image
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'key'

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    products = db.relationship('Product', backref='owner', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qr_content = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route("/upload", methods=['POST'])
def upload():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    file = request.files['file']
    if file:
        try:
            decoded_objects = decode(Image.open(file.stream))
            if decoded_objects:
                qr_content = decoded_objects[0].data.decode('utf-8')

                user = User.query.filter_by(email=session['user_email']).first()
                new_product = Product(qr_content=qr_content, user_id=user.id)
                db.session.add(new_product)
                db.session.commit()

                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)

                flash('Товар успешно добавлен!', 'success')
            else:
                flash('Не удалось декодировать QR-код!', 'danger')
        except Exception as e:
            flash(f'Ошибка при обработке файла: {str(e)}', 'danger')

    return redirect(url_for('second'))

@app.route("/second")
def second():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=session['user_email']).first()
    products = user.products
    return render_template("second.html", products=products)

@app.route("/index")
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



@app.route("/", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember = 'remember' in request.form

        user = User.query.filter_by(email=email).first()

        if user and user.password == password:
            session['user_email'] = user.email
            if remember:
                session.permanent = True
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
            return redirect(url_for('register'))

        if password1 != password2:
            flash('Пароли не совпадают!', 'danger')
            return redirect(url_for('register'))

        new_user = User(email=email, password=password1)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация успешна!', 'success')
        return render_template("gg.html")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop('user_email', None)
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('login'))

@app.route('/add_shelf', methods=['POST'])
def add_shelf():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    name = request.form['name']
    info = request.form['info']
    user = User.query.filter_by(email=session['user_email']).first()
    new_shelf = Product(qr_content=name, user_id=user.id)
    db.session.add(new_shelf)
    db.session.commit()
    return redirect(url_for('second'))

@app.route('/remove_shelf/<int:shelf_id>', methods=['POST'])
def remove_shelf(shelf_id):
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    shelf = Product.query.get_or_404(shelf_id)
    if shelf.user_id == User.query.filter_by(email=session['user_email']).first().id:
        db.session.delete(shelf)
        db.session.commit()
    return redirect(url_for('second'))

@app.route('/remove_all_shelves', methods=['POST'])
def remove_all_shelves():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=session['user_email']).first()
    shelves = Product.query.filter_by(user_id=user.id).all()
    for shelf in shelves:
        db.session.delete(shelf)
    db.session.commit()
    return redirect(url_for('second'))

@app.route('/all_shelves')
def all_shelves():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=session['user_email']).first()
    shelves = Product.query.filter_by(user_id=user.id).all()
    total_products = len(shelves)
    return render_template('all_shelves.html', shelves=shelves, total_products=total_products)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
