# run.py
from app import create_app, db
from app.models import User
from app.utils.security import hash_password

app = create_app()


if __name__ == '__main__':
    app.run(debug=True, port=5002)