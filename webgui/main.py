import threading

from flask import Flask, render_template
from flask_socketio import SocketIO

from lib.network import network_on_connect, network_task

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

stop_event = threading.Event()
tasks = []

@app.route('/')
def index():
    return render_template('index.jinja.html')

@socketio.on('connect')
def connect():
    network_on_connect(socketio)


if __name__ == '__main__':
    try:
        tasks.append(socketio.start_background_task(network_task, socketio, stop_event))
        socketio.run(app)
    finally:
        stop_event.set()
        for t in tasks:
            t.join()