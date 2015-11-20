from flask import Flask, jsonify, request
from requests import codes

app = Flask(__name__)


@app.route('/login', methods=['GET'])
def login():
    return jsonify({})


@app.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    password = request.form['password']
    return jsonify({'username': username, 'password': password}), codes.CREATED

if __name__ == '__main__':
    app.run(host='0.0.0.0')
