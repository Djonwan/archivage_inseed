# app/models/department.py
from app import db


# app/models/department.py
class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    director_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    type = db.Column(db.String(20))

    # RELATION DIRECTEUR
    director = db.relationship('User', foreign_keys=[director_id], backref='directed_departments')
    # backref='directed_departments' → User.directed_departments = liste des départements qu'il dirige

    # RELATION PARENT
    parent = db.relationship('Department', remote_side=[id], backref='children')