from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from flask_cors import CORS
import requests
from babel.dates import format_date
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messages.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)

TELEGRAM_BOT_TOKEN = '7245924381:AAG_eI2Q7m3EezT-pz3OEIjtvHwQxddYfA8'
TELEGRAM_CHAT_ID = '-4260186404'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    message_id = db.Column(db.Integer, nullable=False)

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    endpoint = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json()['result']['message_id']
    return None

def delete_telegram_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    response = requests.post(url, json=payload)
    return response

def notify_subscribers(message):
    subscribers = Subscriber.query.all()
    for subscriber in subscribers:
        payload = {
            'message': message
        }
        try:
            response = requests.post(subscriber.endpoint, json=payload)
            if response.status_code != 200:
                print(f"Failed to notify {subscriber.email}: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"Failed to notify {subscriber.email}: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send_warning', methods=['POST'])
def send_warning():
    region = request.form['region']
    date_str = request.form['date']
    time = request.form['time']
    location = request.form['location']
    description = request.form['description']

    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    formatted_date = format_date(date_obj, format='d MMMM yyyy', locale='ru')

    message = f'''Штормовое предупреждение для {location} в {region}
Дата: {formatted_date}
Время: {time}
Описание: {description}'''

    message_id = send_telegram_message(message)
    if message_id:
        new_message = Message(region=region, date=formatted_date, time=time, location=location, description=description, message_id=message_id)
        db.session.add(new_message)
        db.session.commit()
        notify_subscribers(message)
        flash('Сообщение успешно отправлено!', 'success')
    else:
        flash('Ошибка при отправке сообщения.', 'danger')
    return redirect(url_for('index'))

@app.route('/messages')
def view_messages():
    messages = Message.query.all()
    return render_template('messages.html', messages=messages)

@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    message = Message.query.get(message_id)
    if message:
        response = delete_telegram_message(TELEGRAM_CHAT_ID, message.message_id)
        if response.status_code == 200:
            db.session.delete(message)
            db.session.commit()
            flash('Сообщение успешно удалено.', 'success')
        else:
            flash(f'Ошибка при удалении сообщения: {response.status_code}, {response.text}', 'danger')
    else:
        flash('Сообщение не найдено.', 'danger')
    return redirect(url_for('view_messages'))

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    email = data.get('email')
    endpoint = data.get('endpoint')

    if not email or not endpoint:
        return jsonify({'error': 'Email и endpoint обязательны'}), 400

    if Subscriber.query.filter_by(email=email).first():
        return jsonify({'error': 'Этот email уже подписан'}), 400

    new_subscriber = Subscriber(email=email, endpoint=endpoint)
    db.session.add(new_subscriber)
    db.session.commit()

    return jsonify({'message': 'Успешная подписка'}), 201

@app.route('/docs')
def docs():
    return render_template('docs.html')

if __name__ == '__main__':
    app.run(debug=True)
