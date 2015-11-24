import os

from flask import Flask, jsonify, request
from flask.ext.bcrypt import Bcrypt
from flask.ext.login import (
    LoginManager,
    login_required,
    login_user,
    logout_user,
    make_secure_token,
    UserMixin,
)
from flask.ext.sqlalchemy import SQLAlchemy

from requests import codes

db = SQLAlchemy()


class User(db.Model, UserMixin):
    """
    A user has an email and password.
    """
    email = db.Column(db.String, primary_key=True)
    password_hash = db.Column(db.String)

    def get_auth_token(self):
        """
        See https://flask-login.readthedocs.org/en/latest/#alternative-tokens

        :return: A secure token unique to this ``User`` with the current
            ``password_hash``.
        :rtype: string
        """
        return make_secure_token(self.email, self.password_hash)

    def get_id(self):
        """
        See https://flask-login.readthedocs.org/en/latest/#your-user-class

        :return: the email address to satify Flask-Login's requirements. This
            is used in conjunction with ``load_user`` for session management.
        :rtype: string
        """
        return self.email


def create_app(database_uri):
    """
    Create an application with a database in a given location.

    :param database_uri: The location of the database for the application.
    :type database_uri: string
    :return: An application instance.
    :rtype: ``Flask``
    """
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SECRET_KEY'] = os.environ.get('SECRET', 'secret')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app

SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI',
                                         'sqlite:///:memory:')
app = create_app(database_uri=SQLALCHEMY_DATABASE_URI)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user_from_id(user_id):
    """
    Flask-Login ``user_loader`` callback.

    The ``user_id`` was stored in the session environment by Flask-Login.
    user_loader stores the returned ``User`` object in ``current_user`` during
    every flask request.

    See https://flask-login.readthedocs.org/en/latest/#flask.ext.login.LoginManager.user_loader.  # noqa

    :param user_id: The ID of the user Flask is trying to load.
    :type user_id: string
    :return: The user which has the email address ``user_id`` or ``None`` if
        there is no such user.
    :rtype: ``User`` or ``None``.
    """
    return User.query.filter_by(email=user_id).first()


@login_manager.token_loader
def load_user_from_token(auth_token):
    """
    Flask-Login token-loader callback.

    See https://flask-login.readthedocs.org/en/latest/#flask.ext.login.LoginManager.token_loader  # noqa

    :param auth_token: The authentication token of the user Flask is trying to
        load.
    :type user_id: string
    :return: The user which has the given authentication token or ``None`` if
        there is no such user.
    :rtype: ``User`` or ``None``.
    """
    for user in User.query.all():
        if user.get_auth_token() == auth_token:
            return user


@app.route('/login', methods=['POST'])
def login():
    """
    Log in a given user.

    :param email: An email address to log in as.
    :type email: string
    :param password: A password associated with the given ``email`` address.
    :type password: string
    :resheader Content-Type: application/json
    :resheader Set-Cookie: A ``remember_token``.
    :resjson string email: The email address which has been logged in.
    :resjson string password: The password of the user which has been logged
        in.
    :status 200: A user with the given ``email`` has been logged in.
    :status 404: No user can be found with the given ``email``.
    :status 401: The given ``password`` is incorrect.
    """
    email = request.form['email']
    password = request.form['password']

    user = load_user_from_id(user_id=email)
    if user is None:
        return jsonify(
            title='The requested user does not exist.',
            detail='No user exists with the email "{email}"'.format(
                email=email),
        ), codes.NOT_FOUND

    if not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify(
            title='An incorrect password was provided.',
            detail='The password for the user "{email}" does not match the '
                   'password provided.'.format(email=email),
        ), codes.UNAUTHORIZED

    login_user(user, remember=True)

    return jsonify(email=email, password=password)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    Log the current user out.

    :resheader Content-Type: application/json
    :status 200: The current user has been logged out.
    """
    logout_user()
    return jsonify({}), codes.OK


@app.route('/signup', methods=['POST'])
def signup():
    """
    Sign up a new user.

    :param email: The email address of the new user.
    :type email: string
    :param password: A password to associate with the given ``email`` address.
    :type password: string
    :resheader Content-Type: application/json
    :resjson string email: The email address of the new user.
    :resjson string password: The password of the new user.
    :status 200: A user with the given ``email`` and ``password`` has been
        created.
    :status 409: There already exists a user with the given ``email``.
    """
    email = request.form['email']
    password = request.form['password']

    if load_user_from_id(email) is not None:
        return jsonify({}), codes.CONFLICT

    password_hash = bcrypt.generate_password_hash(password)
    user = User(email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    return jsonify(email=email, password=password), codes.CREATED

if __name__ == '__main__':   # pragma: no cover
    # Specifying 0.0.0.0 as the host tells the operating system to listen on
    # all public IPs. This makes the server visible externally.
    # See http://flask.pocoo.org/docs/0.10/quickstart/#a-minimal-application
    app.run(host='0.0.0.0')
