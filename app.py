from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from PIL import Image
import os
import cv2
import numpy as np
import json
from sqlalchemy import text, inspect
from datetime import datetime, timezone
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)
# Модели
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    users = db.relationship('User', backref='company', lazy=True)
    products = db.relationship('Product', backref='company', lazy=True)
    shelves = db.relationship('Shelf', backref='company', lazy=True)
    def __repr__(self):
        return f'<Company {self.domain}>'
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='worker')
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    products = db.relationship('Product', backref='owner', lazy=True)
    shelves = db.relationship('Shelf', backref='owner', lazy=True)
    requests = db.relationship('Request', foreign_keys='Request.customer_id', backref='customer', lazy=True)
    __table_args__ = (db.UniqueConstraint('email', 'company_id', name='unique_email_per_company'),)
    def __repr__(self):
        return f'<User {self.email}>'
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qr_content = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelf.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    requests = db.relationship('Request', backref='product', lazy=True)
    def __repr__(self):
        return f'<Product {self.qr_content}>'
class Shelf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    products = db.relationship('Product', backref='shelf', lazy=True)
    def __repr__(self):
        return f'<Shelf {self.name}>'
class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='new')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    request_type = db.Column(db.String(50), default='order')
    priority = db.Column(db.String(20), default='medium')
    description = db.Column(db.Text)
    def __repr__(self):
        return f'<Request {self.id}>'
# Папка для загрузок
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
def init_database():
    """Инициализация базы данных с правильной структурой"""
    with app.app_context():
        db.create_all()
        print("✅ База данных инициализирована успешно!")
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
# Главная страница
@app.route("/")
def index():
    return redirect(url_for('login'))
# Регистрация
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        domain = request.form.get('domain', '').strip().lower()
        email = request.form['email']
        password1 = request.form['password1']
        password2 = request.form['password2']
        role = request.form.get('role', 'worker')
        # Валидация данных
        if not domain or not email or not password1:
            flash('Все поля обязательны для заполнения!', 'danger')
            return render_template("register.html")
        if password1 != password2:
            flash('Пароли не совпадают!', 'danger')
            return render_template("register.html")
        try:
            # Проверяем и создаем компанию если нужно
            company = Company.query.filter_by(domain=domain).first()
            if not company:
                company = Company(
                    domain=domain,
                    name=f"Компания {domain.title()}"
                )
                db.session.add(company)
                db.session.commit()
            # Проверяем уникальность email в рамках компании
            existing_user = User.query.filter_by(
                email=email,
                company_id=company.id
            ).first()
            if existing_user:
                flash('Пользователь с таким email уже существует в этой компании!', 'danger')
                return render_template("register.html")
            new_user = User(
                email=email,
                password=password1,
                role=role,
                company_id=company.id
            )
            db.session.add(new_user)
            db.session.commit()
            # АВТОМАТИЧЕСКИ ВХОДИМ ПОСЛЕ РЕГИСТРАЦИИ
            session['user_email'] = new_user.email
            session['user_id'] = new_user.id
            session['user_role'] = new_user.role
            session['company_id'] = company.id
            session['company_domain'] = company.domain
            session['company_name'] = company.name
            flash('Регистрация успешна! Вы автоматически вошли в систему.', 'success')
            # ПРАВИЛЬНЫЕ РЕДИРЕКТЫ В ЗАВИСИМОСТИ ОТ РОЛИ
            if role == 'owner':
                return redirect(url_for('owner_dashboard'))
            elif role == 'worker':
                return redirect(url_for('gg'))
            elif role == 'customer':
                return redirect(url_for('customer_dashboard'))
            else:
                return redirect(url_for('gg'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при регистрации: {str(e)}', 'danger')
            return render_template("register.html")
    return render_template("register.html")
# Вход в систему
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        domain = request.form.get('domain', '').strip().lower()
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'worker')
        remember = 'remember' in request.form
        # Валидация данных
        if not domain or not email or not password:
            flash('Все поля обязательны для заполнения!', 'danger')
            return render_template("login.html")
        # Находим компанию
        company = Company.query.filter_by(domain=domain).first()
        if not company:
            flash('Компания с таким доменом не найдена!', 'danger')
            return render_template("login.html")
        # Ищем пользователя в рамках компании
        user = User.query.filter_by(
            email=email,
            company_id=company.id
        ).first()
        if user and user.password == password and user.role == role:
            session['user_email'] = user.email
            session['user_id'] = user.id
            session['user_role'] = user.role
            session['company_id'] = company.id
            session['company_domain'] = company.domain
            session['company_name'] = company.name
            if remember:
                session.permanent = True
            flash(f'Вход успешен в компанию {company.name}!', 'success')
            # ПРАВИЛЬНЫЕ РЕДИРЕКТЫ В ЗАВИСИМОСТИ ОТ РОЛИ
            if role == 'owner':
                return redirect(url_for('owner_dashboard'))
            elif role == 'worker':
                return redirect(url_for('gg'))
            elif role == 'customer':
                return redirect(url_for('customer_dashboard'))
            else:
                return redirect(url_for('gg'))
        else:
            flash('Неверный email, пароль, роль или домен компании!', 'danger')
            return render_template("login.html")
    return render_template("login.html")
# Выход из системы
@app.route("/logout")
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('login'))
# Маршрут для страницы four
@app.route("/four")
def four():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    return render_template("four.html")
# API маршруты для данных
@app.route('/get_products')
def get_products():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify([])
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role == 'owner' or user.role == 'customer':
        products_data = db.session.query(Product, Shelf, User). \
            outerjoin(Shelf, Product.shelf_id == Shelf.id). \
            join(User, Product.user_id == User.id). \
            filter(Product.company_id == session['company_id']). \
            all()
        products_list = []
        for row in products_data:
            product = row[0]
            shelf = row[1]
            owner = row[2]
            products_list.append({
                'id': product.id,
                'qr_content': product.qr_content,
                'shelf': {
                    'id': shelf.id if shelf else None,
                    'name': shelf.name if shelf else None
                } if shelf else None,
                'owner_email': owner.email,
                'created_at': product.created_at.isoformat() if product.created_at else datetime.now(
                    timezone.utc).isoformat()
            })
        return jsonify(products_list)
    else:
        products = Product.query.filter_by(
            user_id=user.id,
            company_id=session['company_id']
        ).all()
        products_list = []
        for product in products:
            products_list.append({
                'id': product.id,
                'qr_content': product.qr_content,
                'shelf': {
                    'id': product.shelf.id if product.shelf else None,
                    'name': product.shelf.name if product.shelf else None
                } if product.shelf else None,
                'owner_email': user.email,
                'created_at': product.created_at.isoformat() if product.created_at else datetime.now(
                    timezone.utc).isoformat()
            })
        return jsonify(products_list)
@app.route('/api/customer_requests')
def api_customer_requests():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify([])
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'customer':
        return jsonify([])
    requests_data = db.session.query(Request, Product). \
        outerjoin(Product, Request.product_id == Product.id). \
        filter(
        Request.customer_id == user.id,
        Request.company_id == session['company_id']
    ).all()
    requests_list = []
    for row in requests_data:
        req = row[0]
        product = row[1]
        product_info = {
            'name': product.qr_content if product else 'Общая заявка',
            'quantity': 1
        } if product else {
            'name': 'Общая заявка',
            'quantity': 1
        }
        requests_list.append({
            'id': req.id,
            'status': req.status,
            'created_at': req.created_at.isoformat() if req.created_at else datetime.now(timezone.utc).isoformat(),
            'type': req.request_type,
            'priority': req.priority,
            'description': req.description,
            'product_qr_content': product.qr_content if product else 'Общая заявка',
            'product_id': product.id if product else None,
            'products': [product_info]
        })
    return jsonify(requests_list)
@app.route('/api/owner_requests')
def api_owner_requests():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify([])
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'owner':
        return jsonify([])
    requests_data = db.session.query(Request, User, Product). \
        join(User, Request.customer_id == User.id). \
        outerjoin(Product, Request.product_id == Product.id). \
        filter(Request.company_id == session['company_id']). \
        all()
    requests_list = []
    for row in requests_data:
        req = row[0]
        customer = row[1]
        product = row[2]
        requests_list.append({
            'id': req.id,
            'status': req.status,
            'created_at': req.created_at.isoformat() if req.created_at else datetime.now(timezone.utc).isoformat(),
            'type': req.request_type,
            'priority': req.priority,
            'description': req.description,
            'customer_email': customer.email,
            'product_qr_content': product.qr_content if product else 'Общая заявка',
            'product_id': product.id if product else None
        })
    return jsonify(requests_list)
# Основные маршруты
@app.route("/upload_qr", methods=['POST'])
def upload_qr():
    if 'user_email' not in session or 'company_id' not in session:
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
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify([])
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    shelves = Shelf.query.filter_by(user_id=user.id, company_id=session['company_id']).all()
    shelves_data = [{"id": shelf.id, "name": shelf.name} for shelf in shelves]
    return jsonify(shelves_data)
@app.route("/add_product_to_shelf", methods=['POST'])
def add_product_to_shelf():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    data = request.get_json()
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    new_product = Product(
        qr_content=data.get('qr_content', data.get('article', 'No Article')),
        user_id=user.id,
        company_id=session['company_id'],
        shelf_id=data.get('shelf_id')
    )
    db.session.add(new_product)
    db.session.commit()
    return jsonify({"success": True, "message": "Товар успешно добавлен"})
@app.route("/upload", methods=['POST'])
def upload():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    file = request.files['file']
    if file:
        try:
            qr_content = decode_qr_code(Image.open(file.stream))
            if qr_content:
                user = User.query.filter_by(
                    email=session['user_email'],
                    company_id=session['company_id']
                ).first()
                new_product = Product(
                    qr_content=qr_content,
                    user_id=user.id,
                    company_id=session['company_id']
                )
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
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"products": []})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    shelf = db.session.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id or shelf.company_id != session['company_id']:
        return jsonify({"products": []})
    products = Product.query.filter_by(shelf_id=shelf_id, user_id=user.id, company_id=session['company_id']).all()
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
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    products = Product.query.filter_by(user_id=user.id, company_id=session['company_id']).all()
    shelves = Shelf.query.filter_by(user_id=user.id, company_id=session['company_id']).all()
    return render_template("second.html", products=products, shelves=shelves)
@app.route("/gg")
def gg():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'worker':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    shelves = Shelf.query.filter_by(user_id=user.id, company_id=session['company_id']).all()
    return render_template("gg.html", shelves=shelves)
@app.route('/add_shelf', methods=['POST'])
def add_shelf():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    name = request.form['name']
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    new_shelf = Shelf(name=name, user_id=user.id, company_id=session['company_id'])
    db.session.add(new_shelf)
    db.session.commit()
    return jsonify({"success": True, "shelf_id": new_shelf.id})
@app.route('/remove_shelf/<int:shelf_id>', methods=['POST'])
def remove_shelf(shelf_id):
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    shelf = db.session.get(Shelf, shelf_id)
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if not shelf or shelf.user_id != user.id or shelf.company_id != session['company_id']:
        return jsonify({"success": False, "message": "Это не ваша полка."})
    Product.query.filter_by(shelf_id=shelf_id, company_id=session['company_id']).update({'shelf_id': None})
    db.session.delete(shelf)
    db.session.commit()
    return jsonify({"success": True})
@app.route('/remove_all_shelves', methods=['POST'])
def remove_all_shelves():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    Product.query.filter_by(user_id=user.id, company_id=session['company_id']).update({'shelf_id': None})
    Shelf.query.filter_by(user_id=user.id, company_id=session['company_id']).delete()
    db.session.commit()
    return jsonify({"success": True})
@app.route('/all_shelves')
def all_shelves():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    products = Product.query.filter_by(user_id=user.id, company_id=session['company_id']).all()
    total_products = len(products)
    shelves = Shelf.query.filter_by(user_id=user.id, company_id=session['company_id']).all()
    return render_template('all_shelves.html', products=products, total_products=total_products, shelves=shelves)
@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    product = Product.query.filter_by(id=product_id, user_id=user.id, company_id=session['company_id']).first()
    if not product:
        return jsonify({"success": False, "message": "Товар не найден."})
    db.session.delete(product)
    db.session.commit()
    return jsonify({"success": True, "message": "Товар успешно удален."})
@app.route('/update_product', methods=['POST'])
def update_product():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в системе."})
    data = request.get_json()
    product_id = data.get('product_id')
    qr_content = data.get('qr_content')
    shelf_id = data.get('shelf_id')
    if not product_id or not qr_content:
        return jsonify({"success": False, "message": "Отсутствуют обязательные данные"})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    product = Product.query.filter_by(id=product_id, user_id=user.id, company_id=session['company_id']).first()
    if not product:
        return jsonify({"success": False, "message": "Товар не найден"})
    product.qr_content = qr_content
    if shelf_id:
        shelf = Shelf.query.filter_by(id=shelf_id, user_id=user.id, company_id=session['company_id']).first()
        if not shelf:
            return jsonify({"success": False, "message": "Полка не найдена"})
        product.shelf_id = shelf_id
    else:
        product.shelf_id = None
    db.session.commit()
    return jsonify({"success": True, "message": "Товар успешно обновлен"})
@app.route('/move_product_to_shelf', methods=['POST'])
def move_product_to_shelf():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    data = request.get_json()
    product_id = data.get('product_id')
    shelf_id = data.get('shelf_id')
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    product = Product.query.filter_by(id=product_id, user_id=user.id, company_id=session['company_id']).first()
    if not product:
        return jsonify({"success": False, "message": "Товар не найден."})
    if not shelf_id:
        product.shelf_id = None
    else:
        shelf = Shelf.query.filter_by(id=shelf_id, user_id=user.id, company_id=session['company_id']).first()
        if not shelf:
            return jsonify({"success": False, "message": "Полка не найдена."})
        product.shelf_id = shelf_id
    db.session.commit()
    return jsonify({"success": True, "message": "Товар перемещен."})
# Маршруты для владельца
@app.route('/owner_dashboard')
def owner_dashboard():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'owner':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    products = Product.query.filter_by(company_id=session['company_id']).all()
    total_products = len(products)
    requests = Request.query.filter_by(status='new', company_id=session['company_id']).all()
    new_requests_count = len(requests)
    return render_template('owner_dashboard.html',
                           total_products=total_products,
                           new_requests_count=new_requests_count)
@app.route('/owner_products')
def owner_products():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'owner':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    products = Product.query.filter_by(company_id=session['company_id']).all()
    shelves = Shelf.query.filter_by(company_id=session['company_id']).all()
    return render_template('owner_products.html', products=products, shelves=shelves)
@app.route('/owner_requests')
def owner_requests():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'owner':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    requests_data = db.session.query(Request, User, Product). \
        join(User, Request.customer_id == User.id). \
        outerjoin(Product, Request.product_id == Product.id). \
        filter(Request.company_id == session['company_id']). \
        all()
    requests = []
    for row in requests_data:
        req = row[0]
        customer = row[1]
        product = row[2]
        status_map = {
            'new': 'Новая',
            'in-progress': 'В работе',
            'completed': 'Одобрена',
            'cancelled': 'Отклонена'
        }
        requests.append({
            'id': req.id,
            'email': customer.email,
            'qr_content': product.qr_content if product else 'Общая заявка',
            'status': status_map.get(req.status, req.status),
            'created_at': req.created_at,
            'request_type': req.request_type,
            'priority': req.priority,
            'description': req.description
        })
    return render_template('owner_requests.html', requests=requests)
# Маршруты для заказчика
@app.route('/customer_dashboard')
def customer_dashboard():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    products = Product.query.filter_by(company_id=session['company_id']).all()
    total_products = len(products)
    user_requests = Request.query.filter_by(customer_id=user.id, company_id=session['company_id']).all()
    return render_template('customer_dashboard.html',
                           total_products=total_products,
                           user_requests_count=len(user_requests))
@app.route('/customer_products')
def customer_products():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    products_data = db.session.query(Product, Shelf, User). \
        outerjoin(Shelf, Product.shelf_id == Shelf.id). \
        join(User, Product.user_id == User.id). \
        filter(Product.company_id == session['company_id']). \
        all()
    total_products = len(products_data)
    return render_template('customer_products.html',
                           products=products_data,
                           total_products=total_products)
@app.route('/customer_search')
def customer_search():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    search_query = request.args.get('q', '')
    products = []
    if search_query:
        products = db.session.query(Product, Shelf, User). \
            outerjoin(Shelf, Product.shelf_id == Shelf.id). \
            join(User, Product.user_id == User.id). \
            filter(
            Product.qr_content.ilike(f'%{search_query}%'),
            Product.company_id == session['company_id']
        ).all()
    return render_template('customer_search.html',
                           products=products,
                           search_query=search_query,
                           total_found=len(products))
@app.route('/customer_requests')
def customer_requests():
    if 'user_email' not in session or 'company_id' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('login'))
    requests_data = db.session.query(Request, Product). \
        outerjoin(Product, Request.product_id == Product.id). \
        filter(
        Request.customer_id == user.id,
        Request.company_id == session['company_id']
    ).all()
    requests = []
    for row in requests_data:
        req = row[0]
        product = row[1]
        status_map = {
            'new': 'Новая',
            'in-progress': 'В работе',
            'completed': 'Одобрена',
            'cancelled': 'Отклонена'
        }
        requests.append({
            'id': req.id,
            'status': status_map.get(req.status, req.status),
            'qr_content': product.qr_content if product else 'Общая заявка',
            'product_id': req.product_id,
            'created_at': req.created_at,
            'request_type': req.request_type,
            'priority': req.priority,
            'description': req.description
        })
    return render_template('customer_requests.html', requests=requests)
# Маршруты для работы с заявками
@app.route('/create_request/<int:product_id>', methods=['POST'])
def create_request(product_id):
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'customer':
        return jsonify({"success": False, "message": "Только заказчик может создать заявку."})
    product = db.session.get(Product, product_id)
    if not product or product.company_id != session['company_id']:
        return jsonify({"success": False, "message": "Товар не найден."})
    existing_request = Request.query.filter_by(customer_id=user.id, product_id=product_id,
                                               company_id=session['company_id']).first()
    if existing_request:
        return jsonify({"success": False, "message": "Заявка на этот товар уже существует."})
    new_request = Request(
        customer_id=user.id,
        product_id=product.id,
        company_id=session['company_id'],
        status='new',
        request_type='order',
        priority='medium',
        description=f'Заявка на товар: {product.qr_content}'
    )
    db.session.add(new_request)
    db.session.commit()
    return jsonify({"success": True, "message": "Заявка успешно создана."})
@app.route('/create_custom_request', methods=['POST'])
def create_custom_request():
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'customer':
        return jsonify({"success": False, "message": "Только заказчик может создать заявку."})
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Отсутствуют данные запроса."})
        request_type = data.get('type')
        priority = data.get('priority')
        description = data.get('description')
        if not all([request_type, priority, description]):
            return jsonify({"success": False, "message": "Все поля обязательны для заполнения."})
        new_request = Request(
            customer_id=user.id,
            product_id=None,
            company_id=session['company_id'],
            status='new',
            request_type=request_type,
            priority=priority,
            description=description
        )
        db.session.add(new_request)
        db.session.commit()
        return jsonify({"success": True, "message": "Заявка успешно создана."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Ошибка при создании заявки: {str(e)}"})
@app.route('/cancel_request/<int:request_id>', methods=['POST'])
def cancel_request(request_id):
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    request_item = db.session.get(Request, request_id)
    if not request_item or request_item.company_id != session['company_id']:
        return jsonify({"success": False, "message": "Заявка не найдена."})
    if request_item.customer_id != user.id:
        return jsonify({"success": False, "message": "Вы не можете отменить эту заявку."})
    request_item.status = 'cancelled'
    db.session.commit()
    return jsonify({"success": True, "message": "Заявка успешно отменена."})
@app.route('/update_request_status/<int:request_id>', methods=['POST'])
def update_request_status(request_id):
    if 'user_email' not in session or 'company_id' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(
        email=session['user_email'],
        company_id=session['company_id']
    ).first()
    if user.role != 'owner':
        return jsonify({"success": False, "message": "Только владелец может изменить статус заявки."})
    data = request.get_json()
    status = data.get('status')
    status_map = {
        'Одобрена': 'completed',
        'Отклонена': 'cancelled',
        'Новая': 'new',
        'В работе': 'in-progress'
    }
    status_en = status_map.get(status)
    if not status_en:
        return jsonify({"success": False, "message": "Некорректный статус."})
    request_item = db.session.get(Request, request_id)
    if not request_item or request_item.company_id != session['company_id']:
        return jsonify({"success": False, "message": "Заявка не найдена."})
    request_item.status = status_en
    db.session.commit()
    return jsonify({"success": True, "message": "Статус заявки обновлен."})
if __name__ == "__main__":
    init_database()
    print("Сервер запущен! Перейдите по http://localhost:5000")
    app.run(debug=True)
