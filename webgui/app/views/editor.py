from flask import Blueprint, render_template, abort, redirect, url_for

from app.lib.models import EffectStack, EffectGroup, Effect
from app.lib.forms import EffectForm, EffectGroupForm, EffectStackForm
from app import db


app = Blueprint('editor', __name__)


@app.route('/')
def index():
    stacks = EffectStack.query.all()
    groups = EffectGroup.query.all()
    effects = Effect.query.all()
    return render_template('editor/index.jinja.html', stacks=stacks, groups=groups, effects=effects)


@app.route('/edit/<type_>/new', methods=['GET', 'POST'])
@app.route('/edit/<type_>/<int:id>', methods=['GET', 'POST'])
def edit(type_, id=None):
    obj = None
    if type_ == 'effect':
        if id:
            obj = Effect.query.get(id)
        form = EffectForm(obj=obj)

    elif type_ == 'group':
        if id:
            obj = EffectGroup.query.get(id)
        form = EffectGroupForm(obj=obj)

    elif type_ == 'stack':
        if id:
            obj = EffectStack.query.get(id)
        form = EffectStackForm(obj=obj)

    else:
        abort(400, "Invalid type")

    if form.validate_on_submit():
        if type_ == 'effect':
            obj = obj or Effect()
            form.populate_obj(obj)

        elif type_ == 'group':
            obj = obj or EffectGroup()
            form.populate_obj(obj)

        elif type_ == 'stack':
            obj = obj or EffectStack()
            form.populate_obj(obj)

        db.session.add(obj)
        db.session.commit()

        return redirect(url_for('.index'))

    return render_template('editor/form.jinja.html', form=form)
