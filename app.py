from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from PIL import Image
import os
import cv2
import numpy as np
import json
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'key'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    products = db.relationship('Product', backref='owner', lazy=True)
    shelves = db.relationship('Shelf', backref='owner', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qr_content = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelf.id'), nullable=True)

class Shelf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    products = db.relationship('Product', backref='shelf', lazy=True)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def check_and_migrate_db():
    """Проверяет и обновляет структуру базы данных при необходимости"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT shelf_id FROM product LIMIT 1"))
        print("База данных актуальна")
    except Exception as e:
        print(f"Миграция базы данных: {e}")
        db.drop_all()
        db.create_all()
        print("База данных пересоздана")

def decode_qr_code(image):
    try:
        if isinstance(image, Image.Image):
            if image.mode != 'RGB':
                image = image.convert('RGB')
            img_np = np.array(image)
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img_np = image
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img_np)
        if data and bbox is not None:
            return data
        return None
    except Exception as e:
        print(f"QR decoding error: {e}")
        return None

# Маршруты
@app.route("/upload_qr", methods=['POST'])
def upload_qr():
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Файл не загружен"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Пустое имя файла"})
    try:
        qr_content = decode_qr_code(Image.open(file.stream))
        if qr_content:
            try:
                product_data = json.loads(qr_content)
                return jsonify({"success": True, "product": product_data, "qr_content": qr_content})
            except:
                return jsonify({"success": True,
                                "product": {"article": qr_content, "name": f"Товар (QR: {qr_content})", "price": "0"},
                                "qr_content": qr_content})
        else:
            return jsonify({"success": False, "message": "QR-код не найден"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка при обработке файла: {str(e)}"})

@app.route("/get_shelves", methods=['GET'])
def get_shelves():
    if 'user_email' not in session:
        return jsonify([])
    user = User.query.filter_by(email=session['user_email']).first()
    shelves = Shelf.query.filter_by(user_id=user.id).all()
    shelves_data = [{"id": shelf.id, "name": shelf.name} for shelf in shelves]
    return jsonify(shelves_data)

@app.route("/add_product_to_shelf", methods=['POST'])
def add_product_to_shelf():
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    data = request.get_json()
    user = User.query.filter_by(email=session['user_email']).first()
    new_product = Product(
        qr_content=data.get('qr_content', data.get('article', 'No Article')),
        user_id=user.id,
        shelf_id=data.get('shelf_id')
    )
    db.session.add(new_product)
    db.session.commit()
    return jsonify({"success": True, "message": "Товар успешно добавлен"})

@app.route("/upload", methods=['POST'])
def upload():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    file = request.files['file']
    if file:
        try:
            qr_content = decode_qr_code(Image.open(file.stream))
            if qr_content:
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

@app.route("/get_shelf_products/<int:shelf_id>")
def get_shelf_products(shelf_id):
    if 'user_email' not in session:
        return jsonify({"products": []})
    user = User.query.filter_by(email=session['user_email']).first()
    shelf = Shelf.query.get(shelf_id)
    if not shelf or shelf.user_id != user.id:
        return jsonify({"products": []})
    products = Product.query.filter_by(shelf_id=shelf_id, user_id=user.id).all()
    products_data = [
        {
            "name": p.qr_content,
            "article": p.qr_content,
            "qr_content": p.qr_content
        } for p in products
    ]
    return jsonify({"products": products_data})

@app.route("/second")
def second():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    products = Product.query.filter_by(user_id=user.id).all()
    shelves = Shelf.query.filter_by(user_id=user.id).all()
    return render_template("second.html", products=products, shelves=shelves)

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
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    shelves = Shelf.query.filter_by(user_id=user.id).all()
    return render_template("gg.html", shelves=shelves)

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
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    name = request.form['name']
    user = User.query.filter_by(email=session['user_email']).first()
    new_shelf = Shelf(name=name, user_id=user.id)
    db.session.add(new_shelf)
    db.session.commit()
    return jsonify({"success": True, "shelf_id": new_shelf.id})

@app.route('/remove_shelf/<int:shelf_id>', methods=['POST'])
def remove_shelf(shelf_id):
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    shelf = Shelf.query.get_or_404(shelf_id)
    if shelf.user_id == User.query.filter_by(email=session['user_email']).first().id:
        Product.query.filter_by(shelf_id=shelf_id).update({'shelf_id': None})
        db.session.delete(shelf)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Это не ваша полка."})

@app.route('/remove_all_shelves', methods=['POST'])
def remove_all_shelves():
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(email=session['user_email']).first()
    Product.query.filter_by(user_id=user.id).update({'shelf_id': None})
    Shelf.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    return jsonify({"success": True})

@app.route('/all_shelves')
def all_shelves():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    products = Product.query.filter_by(user_id=user.id).all()
    total_products = len(products)
    shelves = Shelf.query.filter_by(user_id=user.id).all()
    return render_template('all_shelves.html', products=products, total_products=total_products, shelves=shelves)

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(email=session['user_email']).first()
    product = Product.query.filter_by(id=product_id, user_id=user.id).first()
    if not product:
        return jsonify({"success": False, "message": "Товар не найден."})
    db.session.delete(product)
    db.session.commit()
    return jsonify({"success": True, "message": "Товар успешно удален."})

@app.route('/update_product', methods=['POST'])
def update_product():
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})

    data = request.get_json()
    product_id = data.get('product_id')
    qr_content = data.get('qr_content')
    shelf_id = data.get('shelf_id')

    if not product_id or not qr_content:
        return jsonify({"success": False, "message": "Отсутствуют обязательные данные"})

    user = User.query.filter_by(email=session['user_email']).first()
    product = Product.query.filter_by(id=product_id, user_id=user.id).first()

    if not product:
        return jsonify({"success": False, "message": "Товар не найден"})

    product.qr_content = qr_content

    if shelf_id:
        shelf = Shelf.query.filter_by(id=shelf_id, user_id=user.id).first()
        if not shelf:
            return jsonify({"success": False, "message": "Полка не найдена"})
        product.shelf_id = shelf_id
    else:
        product.shelf_id = None

    db.session.commit()
    return jsonify({"success": True, "message": "Товар успешно обновлен"})

@app.route('/move_product_to_shelf', methods=['POST'])
def move_product_to_shelf():
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    data = request.get_json()
    product_id = data.get('product_id')
    shelf_id = data.get('shelf_id')
    user = User.query.filter_by(email=session['user_email']).first()
    product = Product.query.filter_by(id=product_id, user_id=user.id).first()
    if not product:
        return jsonify({"success": False, "message": "Товар не найден."})
    if not shelf_id:
        product.shelf_id = None
    else:
        shelf = Shelf.query.filter_by(id=shelf_id, user_id=user.id).first()
        if not shelf:
            return jsonify({"success": False, "message": "Полка не найдена."})
        product.shelf_id = shelf_id
    db.session.commit()
    return jsonify({"success": True, "message": "Товар перемещен."})

if __name__ == "__main__":
    with app.app_context():
        check_and_migrate_db()
    app.run(debug=True)
