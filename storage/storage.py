"""
A storage service for use by a Jenca Cloud authentication service.
"""

import os

from flask import Flask, json, jsonify, request, make_response

from flask.ext.sqlalchemy import SQLAlchemy
from flask_jsonschema import JsonSchema, ValidationError
from flask_negotiate import consumes

from requests import codes

db = SQLAlchemy()


class User(db.Model):
    """
    A user has an email address and a password hash.
    """

    email = db.Column(db.String, primary_key=True)
    password_hash = db.Column(db.String)


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
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app

SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI',
                                         'sqlite:///:memory:')

POSTGRES_HOST = os.environ.get('POSTGRES_HOST', None)
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'username')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'password')
POSTGRES_DATABASE = os.environ.get('POSTGRES_DATABASE', 'jenca-authorisation')

if POSTGRES_HOST is not None:
    if POSTGRES_HOST.find('env:') == 0:
        POSTGRES_HOST = os.environ.get(POSTGRES_HOST.split(':')[1])
    SQLALCHEMY_DATABASE_URI = "postgres://%s:%s@%s/%s" % (
        POSTGRES_USER,
        POSTGRES_PASSWORD,
        POSTGRES_HOST,
        POSTGRES_DATABASE
    )

app = create_app(database_uri=SQLALCHEMY_DATABASE_URI)

# Inputs can be validated using JSON schema.
# Schemas are in app.config['JSONSCHEMA_DIR'].
# See https://github.com/mattupstate/flask-jsonschema for details.
app.config['JSONSCHEMA_DIR'] = os.path.join(app.root_path, 'schemas')
jsonschema = JsonSchema(app)


def load_user_from_id(user_id):
    """
    :param user_id: The ID of the user Flask is trying to load.
    :type user_id: string
    :return: The user which has the email address ``user_id`` or ``None`` if
        there is no such user.
    :rtype: ``User`` or ``None``.
    """
    return User.query.filter_by(email=user_id).first()


@app.errorhandler(ValidationError)
def on_validation_error(error):
    """
    :resjson string title: An explanation that there was a validation error.
    :resjson string message: The precise validation error.
    :status 400:
    """
    return jsonify(
        title='There was an error validating the given arguments.',
        # By default on Python 2 errors will look like:
        # "u'password' is a required property".
        # This removes all "u'"s, and so could be dangerous.
        detail=error.message.replace("u'", "'"),
    ), codes.BAD_REQUEST


@app.route('/users/<email>', methods=['GET', 'DELETE'])
@consumes('application/json')
def specific_user_route(email):
    """
    **DELETE**:

    Delete a particular user.

    :reqheader Content-Type: application/json
    :resheader Content-Type: application/json
    :resjson string email: The email address of the deleted user.
    :resjson string password_hash: The password hash of the deleted user.
    :status 200: The user has been deleted.
    :status 404: There is no user with the given ``email``.

    **GET**:

    Get information about particular user.

    :reqheader Content-Type: application/json
    :resheader Content-Type: application/json
    :resjson string email: The email address of the user.
    :resjson string password_hash: The password hash of the user.
    :status 200: The requested user's information is returned.
    :status 404: There is no user with the given ``email``.
    """
    user = load_user_from_id(email)

    if user is None:
        return jsonify(
            title='The requested user does not exist.',
            detail='No user exists with the email "{email}"'.format(
                email=email),
        ), codes.NOT_FOUND

    elif request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()

    return_data = jsonify(email=user.email, password_hash=user.password_hash)
    return return_data, codes.OK


@jsonschema.validate('users', 'create')
def create_user():
    """
    Create a new user. See ``users_route`` for details.
    """
    email = request.json['email']
    password_hash = request.json['password_hash']

    if load_user_from_id(email) is not None:
        return jsonify(
            title='There is already a user with the given email address.',
            detail='A user already exists with the email "{email}"'.format(
                email=email),
        ), codes.CONFLICT

    user = User(email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    return jsonify(email=email, password_hash=password_hash), codes.CREATED


@app.route('/users', methods=['GET', 'POST'])
@consumes('application/json')
def users_route():
    """
    **POST**:

    Create a new user.

    :param email: The email address of the new user.
    :type email: string
    :param password_hash: A password hash to associate with the given ``email``
        address.
    :type password_hash: string
    :reqheader Content-Type: application/json
    :resheader Content-Type: application/json
    :resjson string email: The email address of the new user.
    :resjson string password_hash: The password hash of the new user.
    :status 200: A user with the given ``email`` and ``password_hash`` has been
        created.
    :status 409: There already exists a user with the given ``email``.

    **GET**:

    Get information about all users.

    :reqheader Content-Type: application/json
    :resheader Content-Type: application/json
    :resjsonarr string email: The email address of a user.
    :resjsonarr string password_hash: The password hash of a user.
    :status 200: Information about all users is returned.
    """

    if request.method == 'POST':
        return create_user()

    # It the method type is not POST it is GET.
    details = [
        {'email': user.email, 'password_hash': user.password_hash} for user
        in User.query.all()]

    return make_response(
        json.dumps(details),
        codes.OK,
        {'Content-Type': 'application/json'})

if __name__ == '__main__':   # pragma: no cover
    # Specifying 0.0.0.0 as the host tells the operating system to listen on
    # all public IPs. This makes the server visible externally.
    # See http://flask.pocoo.org/docs/0.10/quickstart/#a-minimal-application
    app.run(host='0.0.0.0', port=5001)
