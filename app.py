from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import json
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-123'

# Простое файловое хранилище вместо БД
DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'users': [], 'products': []}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def decode_qr_code(file):
    class DecodedObject:
        def __init__(self, data):
            self.data = data.encode('utf-8')
            self.type = 'QRCODE'
    
    filename = file.filename if file else "test"
    filename_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    test_content = f"QR_Content_{filename_hash}"
    return [DecodedObject(test_content)]

# Проверка пользователя
def check_user(email, password):
    data = load_data()
    for user in data['users']:
        if user['email'] == email and user['password'] == password:
            return True
    return False

# Регистрация пользователя
def register_user(email, password):
    data = load_data()
    for user in data['users']:
        if user['email'] == email:
            return False
    data['users'].append({'email': email, 'password': password})
    save_data(data)
    return True

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
            data = load_data()
            user_products = [p for p in data['products'] if p['user_email'] == session['user_email']]
            new_id = max([p['id'] for p in user_products], default=0) + 1
            data['products'].append({
                'id': new_id,
                'qr_content': qr_content,
                'user_email': session['user_email']
            })
            save_data(data)
            flash('Товар успешно добавлен! (тестовый режим)', 'success')
        else:
            flash('Не удалось декодировать QR-код.', 'warning')
    return redirect(url_for('second'))

@app.route("/second")
def second():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    data = load_data()
    products = [p for p in data['products'] if p['user_email'] == session['user_email']]
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
        if check_user(email, password):
            session['user_email'] = email
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
        if password1 != password2:
            flash('Пароли не совпадают!', 'danger')
        elif register_user(email, password1):
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Пользователь с таким email уже существует!', 'danger')
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
    data = load_data()
    user_products = [p for p in data['products'] if p['user_email'] == session['user_email']]
    new_id = max([p['id'] for p in user_products], default=0) + 1
    data['products'].append({
        'id': new_id,
        'qr_content': name,
        'user_email': session['user_email']
    })
    save_data(data)
    flash('Полка успешно добавлена!', 'success')
    return redirect(url_for('second'))

@app.route('/remove_shelf/<int:shelf_id>', methods=['POST'])
def remove_shelf(shelf_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    data = load_data()
    data['products'] = [p for p in data['products'] if not (p['id'] == shelf_id and p['user_email'] == session['user_email'])]
    save_data(data)
    flash('Полка успешно удалена!', 'success')
    return redirect(url_for('second'))

@app.route('/remove_all_shelves', methods=['POST'])
def remove_all_shelves():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    data = load_data()
    data['products'] = [p for p in data['products'] if p['user_email'] != session['user_email']]
    save_data(data)
    flash('Все полки успешно удалены!', 'success')
    return redirect(url_for('second'))

@app.route('/all_shelves')
def all_shelves():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    data = load_data()
    shelves = [p for p in data['products'] if p['user_email'] == session['user_email']]
    return render_template('all_shelves.html', shelves=shelves, total_products=len(shelves))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
