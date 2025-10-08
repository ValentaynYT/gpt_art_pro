from app import app, db
from sqlalchemy import text

with app.app_context():
    # Проверяем существование столбца shelf_id
    try:
        # Пробуем выполнить запрос с shelf_id
        db.session.execute(text("SELECT shelf_id FROM product LIMIT 1"))
        print("Столбец shelf_id уже существует")
    except Exception as e:
        print(f"Столбца нет, добавляем: {e}")
        # Добавляем столбец shelf_id
        db.session.execute(text("ALTER TABLE product ADD COLUMN shelf_id INTEGER"))
        db.session.commit()
        print("Столбец shelf_id успешно добавлен")