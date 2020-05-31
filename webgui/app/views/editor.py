from flask import Blueprint, render_template, abort, redirect, url_for

from app.lib.forms import EffectForm, EffectGroupForm, EffectStackForm
from app import database as db
from app.lib.database import ObjProxy


app = Blueprint('editor', __name__)


@app.route('/')
def index():
    return render_template('editor/index.jinja.html', db=db)


@app.route('/edit/<type_>/new', methods=['GET', 'POST'])
@app.route('/edit/<type_>/<name>', methods=['GET', 'POST'])
def edit(type_, name=None):
    obj = None
    key = None
    form_cls = None
    if type_ == 'effect':
        key = 'effects'
        form_cls = EffectForm

    elif type_ == 'group':
        key = 'effect_groups'
        form_cls = EffectGroupForm

    elif type_ == 'stack':
        key = 'effect_stacks'
        form_cls = EffectStackForm

    else:
        abort(400, "Invalid type")

    if name:
        obj = db[key].get(name)
        if obj:
            obj = ObjProxy(obj)
    form = form_cls(obj=obj)

    if name and obj is None:
        abort(404, "No such " + type_)

    if form.validate_on_submit():
        with db:
            obj = obj or ObjProxy({})
            form.populate_obj(obj)
            db[key][obj.name] = obj.data
            db.save()

        return redirect(url_for('.index'))

    return render_template('editor/form.jinja.html', form=form)
