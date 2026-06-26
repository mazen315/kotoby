from extensions import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    purchases = db.relationship('Purchase', backref='user', lazy=True)
    requests = db.relationship('PurchaseRequest', backref='user', lazy=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    cover_filename = db.Column(db.String(250), nullable=False)
    book_filename = db.Column(db.String(250), nullable=False)
    purchases = db.relationship('Purchase', backref='book', lazy=True)
    requests = db.relationship('PurchaseRequest', backref='book', lazy=True)

class PurchaseRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    receipt_filename = db.Column(db.String(250), nullable=False)
    status = db.Column(db.String(50), default='Pending') # Pending, Approved, Rejected

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
