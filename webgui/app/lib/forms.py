import re

from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired

from launchpad import Color

from app.lib.models import Effect, effect_to_effect_group, EffectGroup, effect_group_to_effect_stack
from app import db


nl_re = re.compile(r'[\r\n]+')


class EffectListField(TextAreaField):
    def process_data(self, value):
        self.data = ''
        if value:
            self.data = '\n'.join((v.effect.name + ':' + (v.lights or '*') for v in value))


class EffectGroupListField(TextAreaField):
    def process_data(self, value):
        self.data = ''
        if value:
            self.data = '\n'.join((v.name for v in value))


class BaseForm(FlaskForm):
    pass


class EffectForm(BaseForm):
    name = StringField('Name', validators=[DataRequired()])
    prop = StringField('Property', validators=[DataRequired()])
    raw_duration = StringField('Duration', description="Duration of effect, valid suffixes are s (seconds), b (beats), m (measures)")
    start = StringField('Starting Value', validators=[DataRequired()], description="May be a comma separated list as supported by a given light type (ex. rgb lights with a color property), or '$current' to start at the current value, or '$random' for a random value")
    end = StringField('Ending Value', description="May be a comma separated list as supported by a given light type, or '$random' to end at a random value")
    done = StringField('Done Value', description="Like end, defaults to end")

    submit = SubmitField('Save')


class EffectGroupForm(BaseForm):
    name = StringField('Name', validators=[DataRequired()])
    raw_color = SelectField('Color', choices=list(zip(Color.COLORS.keys(), Color.COLORS.keys())))
    color_intensity = IntegerField('Color Intensity', description="Color intensity, 1-4", default=4)
    effects = EffectListField('Effects', description="Names of effects in this group, one per line.  Map to lights like 'effect:light1,light2' or 'effect:*' (default)")

    submit = SubmitField('Save')

    def populate_obj(self, obj):
        obj.name = self.name.data
        obj.color = self.raw_color.data + ':' + str(self.color_intensity.data)
        effects = []
        for line in nl_re.split(self.effects.data):
            line = line.strip()
            if line:
                line = line.split(':', 1)
                if len(line) == 2:
                    name, lights = line
                else:
                    name = line[0]
                    lights = '*'

            effects.append(effect_to_effect_group(effect_group=obj, effect=Effect.query.filter(Effect.name == name).first(), lights=lights or '*'))
        obj.effects = effects


class EffectStackForm(BaseForm):
    name = StringField('Name', validators=[DataRequired()])
    groups = EffectGroupListField('groups', description="Names of groups in this stack, one per line")

    submit = SubmitField('Save')

    def populate_obj(self, obj):
        obj.name = self.name.data
        obj.groups = []
        o = 1
        for n in nl_re.split(self.groups.data):
            if n:
                g = EffectGroup.query.filter(EffectGroup.name == n).first()
                if g:
                    db.session.add(effect_group_to_effect_stack(stack=obj, group=g, order=o))
                    o += 1
