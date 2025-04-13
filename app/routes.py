from flask import Blueprint, jsonify, current_app

main = Blueprint('main', __name__)

@main.route('/users')
def get_users():
    conn = current_app.config['DB_CONNECTION']
    cur = conn.cursor()
    cur.execute("SELECT * FROM users;")  # example table
    rows = cur.fetchall()
    cur.close()
    return jsonify(rows)
