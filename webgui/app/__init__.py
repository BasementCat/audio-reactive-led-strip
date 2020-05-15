import threading
import os
import json
import logging
import time

from flask import Flask, render_template, jsonify, request, abort, Response
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from markupsafe import Markup

from launchpad.colors import Color

from app.lib.network import NetworkThread
from app.lib.lp import LPControlThread


logging.basicConfig(level=logging.DEBUG)

db = SQLAlchemy()
network = NetworkThread()
lp = LPControlThread()


def create_app():
    app_obj = Flask(__name__)
    app_obj.config['SECRET_KEY'] = 'secret!'
    app_obj.config['TEMPLATES_AUTO_RELOAD'] = True
    app_obj.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'

    Bootstrap(app_obj)
    db.init_app(app_obj)
    Migrate(app_obj, db)

    def _tojson(obj):
        return json.dumps(obj, indent=4)
    app_obj.jinja_env.filters['tojson'] = _tojson

    def _lp_color(v):
        c, i = v.split(':', 1)
        return Markup('<span class="lp-color" style="background-color: ' + Color.ALL_COLORS_HEX[c] + '">' + i + '</span>')
    app_obj.jinja_env.filters['lp_color'] = _lp_color

    from app.views import index as index_view
    from app.views import api as api_view
    from app.views import editor as editor_view

    app_obj.register_blueprint(index_view.app)
    app_obj.register_blueprint(api_view.app, url_prefix='/api')
    app_obj.register_blueprint(editor_view.app, url_prefix='/editor')

    # Editor

    # @app.route('/editor', methods=['GET', 'POST'])
    # def editor():
    #     editing = None

    #     if request.method == 'POST':
    #         data = json.loads(request.form.get('data'))
    #         if request.form.get('name'):
    #             obj = effects.get(request.form.get('type'), request.form.get('name'))
    #             if obj is None:
    #                 abort(404, "No such object")
    #             obj.update(effects, data)
    #         else:
    #             obj = effects.new(request.form.get('type'), data)
    #         obj.save()

    #     else:
    #         if request.args.get('action') == 'edit':
    #             editing = effects.get(request.args.get('type'), request.args.get('name'))
    #             if editing is None:
    #                 abort(404, "No such object")
    #             print(editing.to_json())

    #     return render_template('editor.jinja.html', effects=effects, editing=editing)

    # # @app.route('/api/effect/effect', methods=['GET', 'POST'])
    # # @app.route('/api/effect/effect/<id>', methods=['GET', 'POST'])
    # # def api_effect(id=None):
    # #     obj = None
    # #     if id:
    # #         obj = effects.effects[id]

    # #     if request.method == 'POST':
    # #         if obj:
    # #             obj._load(request.json())
    # #             obj.save()
    # #         else:
    # #             obj = Effect()
    # #             obj._load(request.json())
    # #             obj.save()
    # #         return jsonify(obj.to_json())
    # #     else:
    # #         if obj:
    # #             return jsonify(obj.to_json())
    # #         return jsonify({k: v.to_json() for k, v in effects.effects})

    # # Socket IO

    # @socketio.on('connect')
    # def connect():
    #     network_on_connect(socketio)

    # @socketio.on('suspend')
    # def suspend(data):
    #     net_send('suspend', *data.get('args', []), **data.get('kwargs', {}))


    # if __name__ == '__main__':
    #     try:
    #         tasks.append(socketio.start_background_task(network_task, socketio, stop_event))
    #         # socketio.run(app, debug=True, use_reloader=True)
    #         socketio.run(app)
    #     finally:
    #         stop_event.set()
    #         for t in tasks:
    #             t.join()

    return app_obj
