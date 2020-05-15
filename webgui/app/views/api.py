import time
import json

from flask import Blueprint, Response, jsonify, request

from app import network, db
from app.lib.models import Effect


app = Blueprint('api', __name__)


@app.route('/poll/<client_id>', methods=['GET'])
def api_poll(client_id):
    ts = time.time()
    def _stream():
        while time.time() - ts < 10:
            data = network.get_for_client(client_id)
            if not data:
                break
            for item in data:
                yield json.dumps(item).encode('utf-8') + b'\n'
    return Response(_stream(), mimetype='application/json')


@app.route('/send', methods=['POST'])
def api_send():
    d = request.json
    network.send_to_server(d.get('command'), *d.get('args', []), **d.get('kwargs', {}))
    return jsonify({'result': 'OK'})


@app.route('/effect', methods=['POST'])
def api_effect():
    # this one's a form... could be refactored
    db.session.add(Effect(
        name=request.form['name'],
        prop=request.form['prop'],
        raw_duration='0s',
        start=request.form['value']
    ))
    db.session.commit();
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode(64), nullable=False, index=True)
    prop = db.Column(db.UnicodeText(), nullable=False)
    raw_duration = db.Column(db.UnicodeText())
    start = db.Column(db.UnicodeText(), nullable=False)
    end = db.Column(db.UnicodeText())
    done = db.Column(db.UnicodeText())