import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from flask import Flask
from werkzeug.security import generate_password_hash
from extensions import db, login_manager, csrf, limiter
from models import User
from routes import main_bp

app = Flask(__name__)

# Security Hardening Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise RuntimeError('Missing required environment variable: SECRET_KEY')
if len(app.config['SECRET_KEY']) < 32:
    raise RuntimeError('SECRET_KEY must be at least 32 characters long.')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Separate static cover directory from private upload directories
app.config['UPLOAD_FOLDER_BOOKS'] = os.path.abspath(os.path.join(app.root_path, 'uploads', 'books'))
app.config['UPLOAD_FOLDER_COVERS'] = os.path.abspath(os.path.join(app.root_path, 'static', 'uploads', 'covers'))
app.config['UPLOAD_FOLDER_RECEIPTS'] = os.path.abspath(os.path.join(app.root_path, 'uploads', 'receipts'))

# Dynamic Upload limit with fallback (default 100MB)
max_upload_mb = int(os.environ.get('MAX_UPLOAD_MB', '100'))
app.config['MAX_CONTENT_LENGTH'] = max_upload_mb * 1024 * 1024

# Session Cookie Security Policies
debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1']
app.config['SESSION_COOKIE_SECURE'] = not debug_mode
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
csrf.init_app(app)
limiter.init_app(app)

# Ensure upload directories exist
for folder in [app.config['UPLOAD_FOLDER_BOOKS'], app.config['UPLOAD_FOLDER_COVERS'], app.config['UPLOAD_FOLDER_RECEIPTS']]:
    os.makedirs(folder, exist_ok=True)

# Legacy uploads migration logic
def migrate_uploads():
    import shutil
    static_books = os.path.abspath(os.path.join(app.root_path, 'static', 'uploads', 'books'))
    static_receipts = os.path.abspath(os.path.join(app.root_path, 'static', 'uploads', 'receipts'))
    
    # Migrate books
    if os.path.exists(static_books) and os.path.abspath(static_books) != os.path.abspath(app.config['UPLOAD_FOLDER_BOOKS']):
        for file in os.listdir(static_books):
            src = os.path.join(static_books, file)
            dst = os.path.join(app.config['UPLOAD_FOLDER_BOOKS'], file)
            if os.path.isfile(src) and not os.path.exists(dst):
                try:
                    shutil.move(src, dst)
                except Exception as e:
                    app.logger.error(f"Error migrating book {file}: {e}")
        try:
            shutil.rmtree(static_books)
        except Exception:
            pass
            
    # Migrate receipts
    if os.path.exists(static_receipts) and os.path.abspath(static_receipts) != os.path.abspath(app.config['UPLOAD_FOLDER_RECEIPTS']):
        for file in os.listdir(static_receipts):
            src = os.path.join(static_receipts, file)
            dst = os.path.join(app.config['UPLOAD_FOLDER_RECEIPTS'], file)
            if os.path.isfile(src) and not os.path.exists(dst):
                try:
                    shutil.move(src, dst)
                except Exception as e:
                    app.logger.error(f"Error migrating receipt {file}: {e}")
        try:
            shutil.rmtree(static_receipts)
        except Exception:
            pass

with app.app_context():
    migrate_uploads()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register blueprint
app.register_blueprint(main_bp)

# Create Admin if not exists (using environment variables)
with app.app_context():
    db.create_all()
    admin_email = os.environ.get('ADMIN_EMAIL')
    admin_password = os.environ.get('ADMIN_PASSWORD')

    if admin_email and admin_password:
        admin_email = admin_email.strip().lower()
        if not User.query.filter_by(email=admin_email).first():
            admin_user = User(
                email=admin_email,
                password=generate_password_hash(admin_password),
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
    else:
        app.logger.warning('Admin account was not created because ADMIN_EMAIL or ADMIN_PASSWORD is not configured.')

if __name__ == '__main__':
    # Use PORT from environment (Replit/hosts provide it) and bind to 0.0.0.0
    port_env = os.environ.get('PORT', '')
    try:
        port = int(port_env) if port_env else 5000
    except ValueError:
        port = 5000
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
