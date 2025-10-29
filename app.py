from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from PIL import Image
import os
import cv2
import numpy as np
import json
from sqlalchemy import text, inspect

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)


# Модели
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='worker')
    products = db.relationship('Product', backref='owner', lazy=True)
    shelves = db.relationship('Shelf', backref='owner', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qr_content = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelf.id'), nullable=True)

    def __repr__(self):
        return f'<Product {self.qr_content}>'


class Shelf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    products = db.relationship('Product', backref='shelf', lazy=True)

    def __repr__(self):
        return f'<Shelf {self.name}>'


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Новая')

    def __repr__(self):
        return f'<Request {self.id}>'


# Папка для загрузок
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def check_and_migrate_db():
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table("user"):
            db.create_all()
            print("Таблицы созданы")
            return

        columns = inspector.get_columns("user")
        column_names = [column['name'] for column in columns]
        if 'role' not in column_names:
            print("Столбец 'role' отсутствует, выполняется миграция...")
            db.drop_all()
            db.create_all()
            print("База данных пересоздана с добавлением столбца 'role'")


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


# ОСНОВНОЙ МАРШРУТ ВХОДА
@app.route("/", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'worker')
        remember = 'remember' in request.form

        # ОТЛАДОЧНЫЕ СООБЩЕНИЯ
        print("=" * 50)
        print(f"ПОПЫТКА ВХОДА:")
        print(f"Email: {email}")
        print(f"Роль из формы: {role}")
        print("=" * 50)

        user = User.query.filter_by(email=email).first()

        if user:
            print(f"НАЙДЕН ПОЛЬЗОВАТЕЛЬ В БАЗЕ:")
            print(f"Email: {user.email}")
            print(f"Роль в базе: {user.role}")
            print(f"Пароль совпадает: {user.password == password}")
            print(f"Роли совпадают: {user.role == role}")
        else:
            print("ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН В БАЗЕ!")

        if user and user.password == password and user.role == role:
            session['user_email'] = user.email
            if remember:
                session.permanent = True
            flash('Вход успешен!', 'success')

            print(f"УСПЕШНЫЙ ВХОД! РЕДИРЕКТ ДЛЯ РОЛИ: {role}")

            if role == 'owner':
                print("ПЕРЕНАПРАВЛЯЕМ НА owner_dashboard")
                return redirect(url_for('owner_dashboard'))
            elif role == 'worker':
                print("ПЕРЕНАПРАВЛЯЕМ НА gg")
                return redirect(url_for('gg'))
            elif role == 'customer':
                print("ПЕРЕНАПРАВЛЯЕМ НА customer_dashboard")
                return redirect(url_for('customer_dashboard'))
        else:
            print("ОШИБКА ВХОДА: неверные данные")
            flash('Неверный email, пароль или роль!', 'danger')

    return render_template("login.html")


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password1 = request.form['password1']
        password2 = request.form['password2']
        role = request.form.get('role', 'worker')

        print(f"РЕГИСТРАЦИЯ: email={email}, role={role}")  # Отладочное сообщение

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Пользователь с таким email уже существует!', 'danger')
            return redirect(url_for('register'))
        if password1 != password2:
            flash('Пароли не совпадают!', 'danger')
            return redirect(url_for('register'))

        # Теперь роль правильно сохраняется
        new_user = User(email=email, password=password1, role=role)
        db.session.add(new_user)
        db.session.commit()

        print(f"СОЗДАН ПОЛЬЗОВАТЕЛЬ: {email} с ролью: {role}")  # Отладочное сообщение

        flash('Регистрация успешна!', 'success')
        return redirect(url_for('login'))
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


# Маршруты для владельца
@app.route('/owner_dashboard')
def owner_dashboard():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'owner':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('gg'))
    products = Product.query.all()
    total_products = len(products)
    requests = Request.query.filter_by(status='Новая').all()
    new_requests_count = len(requests)
    return render_template('owner_dashboard.html',
                           total_products=total_products,
                           new_requests_count=new_requests_count)


@app.route('/owner_products')
def owner_products():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'owner':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('gg'))
    products = Product.query.all()
    shelves = Shelf.query.all()
    return render_template('owner_products.html', products=products, shelves=shelves)


@app.route('/owner_requests')
def owner_requests():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'owner':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('gg'))
    requests = db.session.query(Request, User, Product).join(User, Request.customer_id == User.id).join(Product,
                                                                                                        Request.product_id == Product.id).add_columns(
        Request.id, User.email, Product.qr_content, Request.status
    ).all()
    return render_template('owner_requests.html', requests=requests)


# Маршруты для заказчика
@app.route('/customer_dashboard')
def customer_dashboard():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('gg'))

    # Получаем все товары
    products = Product.query.all()
    total_products = len(products)

    # Получаем заявки пользователя
    user_requests = Request.query.filter_by(customer_id=user.id).all()

    return render_template('customer_dashboard.html',
                           total_products=total_products,
                           user_requests_count=len(user_requests))


@app.route('/customer_products')
def customer_products():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('gg'))

    # Получаем все товары с информацией о полках и владельцах
    products = db.session.query(Product, Shelf, User). \
        outerjoin(Shelf, Product.shelf_id == Shelf.id). \
        join(User, Product.user_id == User.id). \
        add_columns(
        Product.id,
        Product.qr_content,
        Shelf.name.label('shelf_name'),
        User.email.label('owner_email')
    ).all()

    total_products = len(products)

    return render_template('customer_products.html',
                           products=products,
                           total_products=total_products)


@app.route('/customer_search')
def customer_search():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('gg'))

    search_query = request.args.get('q', '')
    products = []

    if search_query:
        # Поиск по содержимому QR-кода
        products = db.session.query(Product, Shelf, User). \
            outerjoin(Shelf, Product.shelf_id == Shelf.id). \
            join(User, Product.user_id == User.id). \
            filter(Product.qr_content.ilike(f'%{search_query}%')). \
            add_columns(
            Product.id,
            Product.qr_content,
            Shelf.name.label('shelf_name'),
            User.email.label('owner_email')
        ).all()

    return render_template('customer_search.html',
                           products=products,
                           search_query=search_query,
                           total_found=len(products))


@app.route('/customer_requests')
def customer_requests():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'customer':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('gg'))

    # Получаем заявки текущего пользователя с информацией о товарах
    requests = db.session.query(Request, Product). \
        join(Product, Request.product_id == Product.id). \
        filter(Request.customer_id == user.id). \
        add_columns(
        Request.id,
        Request.status,
        Product.qr_content,
        Request.product_id
    ).all()

    return render_template('customer_requests.html', requests=requests)


# Маршруты для работы с заявками
@app.route('/create_request/<int:product_id>', methods=['POST'])
def create_request(product_id):
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'customer':
        return jsonify({"success": False, "message": "Только заказчик может создать заявку."})
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"success": False, "message": "Товар не найден."})

    # Проверяем, нет ли уже активной заявки на этот товар
    existing_request = Request.query.filter_by(customer_id=user.id, product_id=product_id).first()
    if existing_request:
        return jsonify({"success": False, "message": "Заявка на этот товар уже существует."})

    new_request = Request(customer_id=user.id, product_id=product.id, status='Новая')
    db.session.add(new_request)
    db.session.commit()
    return jsonify({"success": True, "message": "Заявка успешно создана."})


@app.route('/cancel_request/<int:request_id>', methods=['POST'])
def cancel_request(request_id):
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(email=session['user_email']).first()
    request_item = Request.query.get(request_id)

    if not request_item:
        return jsonify({"success": False, "message": "Заявка не найдена."})

    if request_item.customer_id != user.id:
        return jsonify({"success": False, "message": "Вы не можете отменить эту заявку."})

    db.session.delete(request_item)
    db.session.commit()
    return jsonify({"success": True, "message": "Заявка успешно отменена."})


@app.route('/update_request_status/<int:request_id>', methods=['POST'])
def update_request_status(request_id):
    if 'user_email' not in session:
        return jsonify({"success": False, "message": "Пожалуйста, войдите в систему."})
    user = User.query.filter_by(email=session['user_email']).first()
    if user.role != 'owner':
        return jsonify({"success": False, "message": "Только владелец может изменить статус заявки."})
    data = request.get_json()
    status = data.get('status')
    if not status or status not in ['Одобрена', 'Отклонена']:
        return jsonify({"success": False, "message": "Некорректный статус."})
    request_item = Request.query.get(request_id)
    if not request_item:
        return jsonify({"success": False, "message": "Заявка не найдена."})
    request_item.status = status
    db.session.commit()
    return jsonify({"success": True, "message": "Статус заявки обновлен."})


# Маршрут для создания тестового владельца
@app.route("/create_test_owner")
def create_test_owner():
    # Проверяем, есть ли уже пользователь с ролью owner
    existing_owner = User.query.filter_by(role='owner').first()
    if existing_owner:
        return f"Владелец уже существует: {existing_owner.email}"

    # Создаем тестового владельца
    test_owner = User(email='owner@test.com', password='123', role='owner')
    db.session.add(test_owner)
    db.session.commit()
    return "Тестовый владелец создан: owner@test.com / 123"


@app.route("/create_test_customer")
def create_test_customer():
    # Проверяем, есть ли уже пользователь с ролью customer
    existing_customer = User.query.filter_by(role='customer').first()
    if existing_customer:
        return f"Заказчик уже существует: {existing_customer.email}"

    # Создаем тестового заказчика
    test_customer = User(email='customer@test.com', password='123', role='customer')
    db.session.add(test_customer)
    db.session.commit()
    return "Тестовый заказчик создан: customer@test.com / 123"


if __name__ == "__main__":
    with app.app_context():
        check_and_migrate_db()
    app.run(debug=True)
