# app/routes/dashboard.py
from flask import Blueprint
from flask_login import login_required

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    from app.routes.drive import home  
    return home()  