# app/__init__.py
from flask import Flask
import logging

# Import the filters
from config import get_config
from app.utils.filters import format_filesize, format_filedate


def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Register Jinja2 filters
    app.jinja_env.filters['filesize'] = format_filesize
    app.jinja_env.filters['filedate'] = format_filedate

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.exams import exams_bp
    from app.routes.analysis import analysis_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(exams_bp, url_prefix='/exams')
    app.register_blueprint(analysis_bp, url_prefix='/analysis')

    return app