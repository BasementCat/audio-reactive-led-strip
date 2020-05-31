import time
import json
import copy

from flask import Blueprint, Response, jsonify, request

from app import network, database as db


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
    with db:
        db['effects'][d['name']] = copy.deepcopy(d)
        db.save()
    return jsonify({'result': 'OK'})
