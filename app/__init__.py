import os
import logging
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import models and create db instance
from .models import db, bcrypt

# Import auth utils
from .routes.auth import is_token_blacklisted

def create_app():
    app = Flask(__name__)
    
    # Configure logging for debug mode
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    app.logger.setLevel(logging.DEBUG)
    
    # Log all incoming requests
    @app.before_request
    def log_request_info():
        app.logger.debug('Request: %s %s', request.method, request.url)
        app.logger.debug('Headers: %s', dict(request.headers))
        if request.get_data():
            app.logger.debug('Body: %s', request.get_data())

    @app.after_request
    def no_cache(response):
        response.cache_control.no_store = True
        response.cache_control.no_cache = True
        response.cache_control.private = True
        response.cache_control.must_revalidate = True
        response.cache_control.max_age = 0
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    CORS(app)
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost", "http://localhost:3000", "http://localhost:80","http://localhost:8080", "http://dechivo.com", "https://dechivo.com", "http://splash25-frontend:8080", "http://frontend:8080"]}})

    # Configure SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'postgresql://splash25user:splash25password@localhost:5432/splash25_core_db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ECHO'] = os.getenv('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    
    # Configure JWT
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600  # 1 hour
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 2592000  # 30 days
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    jwt = JWTManager(app)
    migrate = Migrate(app, db)
    
    # Register token blacklist loader
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return is_token_blacklisted(jwt_header, jwt_payload)
    
    # Register blueprints
    from .routes import main, auth, buyer, seller, admin, system, timeslot, meeting, buyers
    from .routes.health import health_bp
    from .routes.stall import stall
    from .routes.stall_types import stall_types
    
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(buyer)
    app.register_blueprint(seller)
    app.register_blueprint(admin)
    app.register_blueprint(system)
    app.register_blueprint(timeslot)
    app.register_blueprint(meeting)
    app.register_blueprint(buyers)
    app.register_blueprint(stall)
    app.register_blueprint(stall_types)
    app.register_blueprint(health_bp, url_prefix='/api')
    
    # Create database tables (only if database is available)
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            # Database not available - this is fine for testing configuration
            app.logger.warning(f"Database not available during initialization: {e}")
    
    return app
