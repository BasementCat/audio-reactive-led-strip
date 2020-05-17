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
    d = request.json
    db.session.add(Effect(
        name=d['name'],
        prop=d['property'],
        raw_duration=d['duration'],
        start=d['start'],
        end=d['end'],
        done=d['done']
    ))
    db.session.commit()
    return jsonify({'result': 'OK'})
