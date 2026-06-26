import os
import re
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, abort
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import User, Book, PurchaseRequest, Purchase
from extensions import db, limiter

main_bp = Blueprint('main', __name__)

# Allowed file extensions for validation
ALLOWED_RECEIPT_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
ALLOWED_COVER_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_BOOK_EXTENSIONS = {'pdf', 'epub', 'mobi', 'zip'}

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def is_password_strong(password):
    # Enforces at least 8 characters, with at least one letter and one number
    if len(password) < 8:
        return False
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_letter and has_digit

@main_bp.route('/')
def index():
    books = Book.query.all()
    return render_template('index.html', books=books)

@main_bp.route('/book/<int:book_id>')
def book_details(book_id):
    book = Book.query.get_or_404(book_id)
    has_purchased = False
    pending_request = False
    if current_user.is_authenticated:
        if Purchase.query.filter_by(user_id=current_user.id, book_id=book.id).first():
            has_purchased = True
        elif PurchaseRequest.query.filter_by(user_id=current_user.id, book_id=book.id, status='Pending').first():
            pending_request = True
    return render_template('book.html', book=book, has_purchased=has_purchased, pending_request=pending_request)

@main_bp.route('/buy/<int:book_id>', methods=['GET', 'POST'])
@login_required
def buy(book_id):
    book = Book.query.get_or_404(book_id)
    if Purchase.query.filter_by(user_id=current_user.id, book_id=book.id).first():
        flash('You already own this book.', 'info')
        return redirect(url_for('main.book_details', book_id=book.id))
    
    if request.method == 'POST':
        if 'receipt' not in request.files:
            flash('No receipt uploaded', 'danger')
            return redirect(request.url)
        file = request.files['receipt']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file:
            # Secure upload: validate extension
            if not allowed_file(file.filename, ALLOWED_RECEIPT_EXTENSIONS):
                flash('امتداد الملف غير مسموح به! الامتدادات المسموحة للإيصال هي: png, jpg, jpeg, gif, webp, pdf', 'danger')
                return redirect(request.url)
                
            orig_filename = secure_filename(file.filename)
            # Create a secure, unique filename with UUID prefix to prevent guessing and naming collisions
            file_ext = orig_filename.rsplit('.', 1)[1].lower() if '.' in orig_filename else 'png'
            unique_filename = f"receipt_{uuid.uuid4().hex}.{file_ext}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER_RECEIPTS'], unique_filename))
            
            new_request = PurchaseRequest(user_id=current_user.id, book_id=book.id, receipt_filename=unique_filename)
            db.session.add(new_request)
            db.session.commit()
            
            flash('Your receipt has been uploaded and is pending admin approval.', 'success')
            return redirect(url_for('main.book_details', book_id=book.id))

    return render_template('buy.html', book=book)

@main_bp.route('/download/<int:book_id>')
@login_required
def download(book_id):
    book = Book.query.get_or_404(book_id)
    # Check if user purchased or is admin
    if current_user.is_admin or Purchase.query.filter_by(user_id=current_user.id, book_id=book.id).first():
        # Prevent directory traversal attacks
        safe_filename = secure_filename(book.book_filename)
        return send_from_directory(current_app.config['UPLOAD_FOLDER_BOOKS'], safe_filename, as_attachment=True)
    flash('You have not purchased this book yet.', 'danger')
    return redirect(url_for('main.book_details', book_id=book.id))

# --- Auth Routes ---
@main_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        # Normalize email
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('main.admin_dashboard'))
            return redirect(url_for('main.index'))
        else:
            flash('Login failed. Check your email and password.', 'danger')
    return render_template('login.html')

@main_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        # Normalize and validate email
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash('البريد الإلكتروني المدخل غير صالح.', 'danger')
            return redirect(url_for('main.register'))
            
        # Password strength validation
        if not is_password_strong(password):
            flash('كلمة المرور ضعيفة! يجب أن تتكون من 8 خانات على الأقل وتحتوي على رقم وحرف.', 'danger')
            return redirect(url_for('main.register'))
            
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists', 'danger')
            return redirect(url_for('main.register'))
            
        # Use default Werkzeug password hashing parameters (uses strongest available defaults)
        new_user = User(email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('main.index'))
    return render_template('register.html')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

# --- User Dashboard Route ---
@main_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('main.admin_dashboard'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_password or not new_password or not confirm_password:
            flash('Please fill all password fields.', 'danger')
            return redirect(url_for('main.dashboard'))

        if not check_password_hash(current_user.password, current_password):
            flash('كلمة المرور الحالية غير صحيحة', 'danger')
            return redirect(url_for('main.dashboard'))

        if new_password != confirm_password:
            flash('كلمات المرور غير متطابقة', 'danger')
            return redirect(url_for('main.dashboard'))

        # Validate strength of new password
        if not is_password_strong(new_password):
            flash('كلمة المرور الجديدة ضعيفة! يجب أن تتكون من 8 خانات على الأقل وتحتوي على رقم وحرف.', 'danger')
            return redirect(url_for('main.dashboard'))

        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('تم تحديث كلمة المرور بنجاح!', 'success')
        return redirect(url_for('main.dashboard'))

    # GET: show purchases and requests
    purchases = Purchase.query.filter_by(user_id=current_user.id).all()
    purchase_requests = PurchaseRequest.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', purchases=purchases, purchase_requests=purchase_requests)

# --- Admin Routes ---
@main_bp.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    
    pending_requests = PurchaseRequest.query.filter_by(status='Pending').all()
    books = Book.query.all()
    return render_template('admin_dashboard.html', pending_requests=pending_requests, books=books)

@main_bp.route('/admin/add_book', methods=['POST'])
@login_required
def admin_add_book():
    if not current_user.is_admin:
        abort(403)
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    price_str = request.form.get('price', '').strip()
    cover = request.files.get('cover')
    book_file = request.files.get('book_file')

    if not title or not description or not price_str or not cover or not book_file:
        flash('الرجاء ملء جميع الحقول المطلوبة ورفع الملفات.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    try:
        price = float(price_str)
    except ValueError:
        flash('السعر المدخل غير صالح.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    if cover and book_file:
        # Validate extensions to prevent execution vulnerabilities
        if not allowed_file(cover.filename, ALLOWED_COVER_EXTENSIONS):
            flash('امتداد صورة الغلاف غير مسموح به! الصيغ المسموحة: png, jpg, jpeg, gif, webp', 'danger')
            return redirect(url_for('main.admin_dashboard'))
        if not allowed_file(book_file.filename, ALLOWED_BOOK_EXTENSIONS):
            flash('امتداد ملف الكتاب غير مسموح به! الصيغ المسموحة: pdf, epub, mobi, zip', 'danger')
            return redirect(url_for('main.admin_dashboard'))

        cover_orig = secure_filename(cover.filename)
        book_orig = secure_filename(book_file.filename)
        
        # Use UUID to prevent direct directory enumerations or overwriting existing files
        cover_filename = f"cover_{uuid.uuid4().hex}_{cover_orig}"
        book_filename = f"book_{uuid.uuid4().hex}_{book_orig}"
        
        cover.save(os.path.join(current_app.config['UPLOAD_FOLDER_COVERS'], cover_filename))
        book_file.save(os.path.join(current_app.config['UPLOAD_FOLDER_BOOKS'], book_filename))
        
        new_book = Book(title=title, description=description, price=price, 
                        cover_filename=cover_filename, book_filename=book_filename)
        db.session.add(new_book)
        db.session.commit()
        flash('Book added successfully!', 'success')
    else:
        flash('Missing cover or book file.', 'danger')
        
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/approve/<int:req_id>', methods=['POST'])
@login_required
def admin_approve(req_id):
    if not current_user.is_admin:
        abort(403)
    
    req = PurchaseRequest.query.get_or_404(req_id)
    req.status = 'Approved'
    if not Purchase.query.filter_by(user_id=req.user_id, book_id=req.book_id).first():
        new_purchase = Purchase(user_id=req.user_id, book_id=req.book_id)
        db.session.add(new_purchase)
    db.session.commit()
    flash('Purchase approved!', 'success')
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/reject/<int:req_id>', methods=['POST'])
@login_required
def admin_reject(req_id):
    if not current_user.is_admin:
        abort(403)
    
    req = PurchaseRequest.query.get_or_404(req_id)
    req.status = 'Rejected'
    db.session.commit()
    flash('Purchase rejected.', 'info')
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/change_password', methods=['POST'])
@login_required
def admin_change_password():
    if not current_user.is_admin:
        abort(403)
    new_password = request.form.get('new_password')
    if new_password:
        if not is_password_strong(new_password):
            flash('كلمة المرور الجديدة ضعيفة! يجب أن تتكون من 8 خانات على الأقل وتحتوي على رقم وحرف.', 'danger')
            return redirect(url_for('main.admin_dashboard'))
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('Password changed successfully!', 'success')
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/delete_book/<int:book_id>', methods=['POST'])
@login_required
def admin_delete_book(book_id):
    if not current_user.is_admin:
        abort(403)
    
    book = Book.query.get_or_404(book_id)
    
    # Delete files from disk (securely clean filenames)
    try:
        cover_path = os.path.join(current_app.config['UPLOAD_FOLDER_COVERS'], secure_filename(book.cover_filename))
        book_path = os.path.join(current_app.config['UPLOAD_FOLDER_BOOKS'], secure_filename(book.book_filename))
        
        if os.path.exists(cover_path):
            os.remove(cover_path)
        if os.path.exists(book_path):
            os.remove(book_path)
            
        # Delete related purchase requests receipt files
        reqs = PurchaseRequest.query.filter_by(book_id=book_id).all()
        for req in reqs:
            if req.receipt_filename:
                receipt_path = os.path.join(current_app.config['UPLOAD_FOLDER_RECEIPTS'], secure_filename(req.receipt_filename))
                if os.path.exists(receipt_path):
                    os.remove(receipt_path)
    except Exception as e:
        flash(f'خطأ في حذف الملفات: {str(e)}', 'warning')
    
    # Delete all related purchase requests and purchases (cascade delete)
    PurchaseRequest.query.filter_by(book_id=book_id).delete()
    Purchase.query.filter_by(book_id=book_id).delete()
    
    # Delete the book
    db.session.delete(book)
    db.session.commit()
    
    flash('تم حذف الكتاب بنجاح!', 'success')
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/edit_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_book(book_id):
    if not current_user.is_admin:
        abort(403)
    
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '').strip()
        
        if not title or not description or not price_str:
            flash('الرجاء ملء جميع الحقول المطلوبة.', 'danger')
            return redirect(url_for('main.admin_edit_book', book_id=book_id))
        
        try:
            price = float(price_str)
        except ValueError:
            flash('السعر يجب أن يكون رقماً صحيحاً.', 'danger')
            return redirect(url_for('main.admin_edit_book', book_id=book_id))
        
        book.title = title
        book.description = description
        book.price = price
        
        # Handle optional new cover image
        new_cover = request.files.get('cover')
        if new_cover and new_cover.filename:
            if not allowed_file(new_cover.filename, ALLOWED_COVER_EXTENSIONS):
                flash('امتداد صورة الغلاف غير مسموح به! الصيغ المسموحة: png, jpg, jpeg, gif, webp', 'danger')
                return redirect(url_for('main.admin_edit_book', book_id=book_id))
            
            # Delete old cover if exists
            old_cover_path = os.path.join(current_app.config['UPLOAD_FOLDER_COVERS'], secure_filename(book.cover_filename))
            if os.path.exists(old_cover_path):
                try:
                    os.remove(old_cover_path)
                except Exception:
                    pass
            cover_filename = secure_filename(new_cover.filename)
            cover_filename = f"cover_{uuid.uuid4().hex}_{cover_filename}"
            new_cover.save(os.path.join(current_app.config['UPLOAD_FOLDER_COVERS'], cover_filename))
            book.cover_filename = cover_filename
        
        # Handle optional new book file
        new_book_file = request.files.get('book_file')
        if new_book_file and new_book_file.filename:
            if not allowed_file(new_book_file.filename, ALLOWED_BOOK_EXTENSIONS):
                flash('امتداد ملف الكتاب غير مسموح به! الصيغ المسموحة: pdf, epub, mobi, zip', 'danger')
                return redirect(url_for('main.admin_edit_book', book_id=book_id))
            
            # Delete old book file if exists
            old_book_path = os.path.join(current_app.config['UPLOAD_FOLDER_BOOKS'], secure_filename(book.book_filename))
            if os.path.exists(old_book_path):
                try:
                    os.remove(old_book_path)
                except Exception:
                    pass
            book_filename = secure_filename(new_book_file.filename)
            book_filename = f"book_{uuid.uuid4().hex}_{book_filename}"
            new_book_file.save(os.path.join(current_app.config['UPLOAD_FOLDER_BOOKS'], book_filename))
            book.book_filename = book_filename
        
        db.session.commit()
        flash('تم تحديث بيانات الكتاب بنجاح!', 'success')
        return redirect(url_for('main.admin_dashboard'))
    
    return render_template('edit_book.html', book=book)

@main_bp.route('/admin/delete_all_books', methods=['POST'])
@login_required
def admin_delete_all_books():
    if not current_user.is_admin:
        abort(403)
    
    books = Book.query.all()
    
    # Delete files from disk for all books
    for book in books:
        try:
            cover_path = os.path.join(current_app.config['UPLOAD_FOLDER_COVERS'], secure_filename(book.cover_filename))
            book_path = os.path.join(current_app.config['UPLOAD_FOLDER_BOOKS'], secure_filename(book.book_filename))
            
            if os.path.exists(cover_path):
                try:
                    os.remove(cover_path)
                except Exception:
                    pass
            if os.path.exists(book_path):
                try:
                    os.remove(book_path)
                except Exception:
                    pass
        except Exception as e:
            current_app.logger.error(f"Error deleting files for book {book.id}: {e}")
            
    # Delete all receipt files from disk
    reqs = PurchaseRequest.query.all()
    for req in reqs:
        if req.receipt_filename:
            try:
                receipt_path = os.path.join(current_app.config['UPLOAD_FOLDER_RECEIPTS'], secure_filename(req.receipt_filename))
                if os.path.exists(receipt_path):
                    os.remove(receipt_path)
            except Exception as e:
                current_app.logger.error(f"Error deleting receipt {req.receipt_filename}: {e}")

    # Delete all database records
    try:
        PurchaseRequest.query.delete()
        Purchase.query.delete()
        Book.query.delete()
        db.session.commit()
        flash('تم حذف جميع الكتب والطلبات والمشتريات بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ أثناء حذف السجلات من قاعدة البيانات: {str(e)}', 'danger')
        
    return redirect(url_for('main.admin_dashboard'))

# --- Secure view receipt route for admins ---
@main_bp.route('/admin/receipt/<filename>')
@login_required
def view_receipt(filename):
    if not current_user.is_admin:
        abort(403)
    # Prevent path traversal attacks
    filename = secure_filename(filename)
    return send_from_directory(current_app.config['UPLOAD_FOLDER_RECEIPTS'], filename)
