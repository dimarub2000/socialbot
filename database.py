import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'bot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    credit = db.Column(db.Integer, default=200, nullable=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.Integer, nullable=False)
    chat_id = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    credit = db.Column(db.Integer, default=200, nullable=False)
    state = db.Column(db.Integer, default=0, nullable=False)
