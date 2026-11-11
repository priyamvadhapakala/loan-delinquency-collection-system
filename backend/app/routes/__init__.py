from app.routes.collection_routes import collection_bp
from app.routes.business_routes import business_bp
from app.routes.customer_routes import customer_bp
from app.routes.installment_routes import installment_bp
from app.routes.loan_routes import loan_bp
from app.routes.payment_routes import payment_bp


def register_blueprints(app):
    app.register_blueprint(customer_bp)
    app.register_blueprint(loan_bp)
    app.register_blueprint(installment_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(collection_bp)
    app.register_blueprint(business_bp)
