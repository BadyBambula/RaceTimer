from flask import Flask

from race_routes import race_bp

app = Flask('RaceTimer', static_folder='static', template_folder='templates')
app.register_blueprint(race_bp)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
