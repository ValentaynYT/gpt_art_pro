from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from PIL import Image
import os
import numpy as np

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

# Временно отключаем QR-декодирование
def decode_qr_code(image):
    """
    Заглушка для QR-декодера
    """
    # В реальном приложении здесь будет OpenCV
    # Сейчас возвращаем тестовые данные
    class DecodedObject:
        def __init__(self, data):
            self.data = data.encode('utf-8')
            self.type = 'QRCODE'
    
    # Возвращаем тестовый QR код
    return [DecodedObject("Test QR Content")]

@app.route("/upload", methods=['POST'])
def upload():
    if 'user_email' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('login'))

    file = request.files['file']
    if file:
        try:
            # Используем заглушку вместо реального декодера
            decoded_objects = decode_qr_code(Image.open(file.stream))
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

# ... остальные маршруты без изменений ...

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
