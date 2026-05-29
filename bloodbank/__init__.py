from flask import Flask, render_template

from .config import BASE_DIR, Config
from .db import close_db, init_db


def create_app(config_object=Config) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(config_object)

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db(seed=True)

    from .routes.admin import bp as admin_bp
    from .routes.appointments import bp as appointments_bp
    from .routes.auth import bp as auth_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.donations import bp as donations_bp
    from .routes.donors import bp as donors_bp
    from .routes.health import bp as health_bp
    from .routes.inventory import bp as inventory_bp
    from .routes.notifications import bp as notifications_bp
    from .routes.requests import bp as requests_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(donors_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(donations_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
