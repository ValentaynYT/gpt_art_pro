from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='worker')  # owner, worker, customer
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
    status = db.Column(db.String(20), nullable=False, default='Новая')  # Новая, Одобрена, Отклонена
    customer = db.relationship('User', foreign_keys=[customer_id])
    product = db.relationship('Product', foreign_keys=[product_id])

    def __repr__(self):
        return f'<Request {self.id}>'
