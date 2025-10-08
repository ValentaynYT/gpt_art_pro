from app import app, db, Shelf

with app.app_context():
    # Удаляем все полки из базы данных
    db.session.query(Shelf).delete()
    db.session.commit()
    print("Все полки успешно удалены из базы данных.")
