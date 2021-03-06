import re

from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired

from launchpad import Color


nl_re = re.compile(r'[\r\n]+')


class EffectListField(TextAreaField):
    def process_data(self, value):
        self.data = ''
        if value:
            self.data = '\n'.join((v['effect'] + ':' + (','.join(v['lights']) if v['lights'] else '*') for v in value))


class EffectGroupListField(TextAreaField):
    def process_data(self, value):
        self.data = ''
        if value:
            self.data = '\n'.join((v['effect_group'] for v in value))


class BaseForm(FlaskForm):
    pass


class EffectForm(BaseForm):
    name = StringField('Name', validators=[DataRequired()])
    property = StringField('Property', validators=[DataRequired()])
    duration = StringField('Duration', description="Duration of effect, valid suffixes are s (seconds), b (beats), m (measures)")
    start = StringField('Starting Value', validators=[DataRequired()], description="May be a comma separated list as supported by a given light type (ex. rgb lights with a color property), or '$current' to start at the current value, or '$random' for a random value")
    end = StringField('Ending Value', description="May be a comma separated list as supported by a given light type, or '$random' to end at a random value")
    done = StringField('Done Value', description="Like end, defaults to end")

    submit = SubmitField('Save')


class EffectGroupForm(BaseForm):
    name = StringField('Name', validators=[DataRequired()])
    color = SelectField('Color', choices=list(zip(Color.COLORS.keys(), Color.COLORS.keys())))
    color_intensity = IntegerField('Color Intensity', description="Color intensity, 1-4", default=4)
    effects = EffectListField('Effects', description="Names of effects in this group, one per line.  Map to lights like 'effect:light1,light2' or 'effect:*' (default)")

    submit = SubmitField('Save')

    def populate_obj(self, obj):
        obj.name = self.name.data
        obj.color = self.color.data
        obj.color_intensity = self.color_intensity.data
        effects = []
        for line in nl_re.split(self.effects.data):
            line = line.strip()
            if line:
                line = line.split(':', 1)
                if len(line) == 2:
                    name, lights = line
                    lights = lights.split(',')
                else:
                    name = line[0]
                    lights = ['*']

            effects.append({'effect': name, 'lights': lights})
        obj.effects = effects


class EffectStackForm(BaseForm):
    name = StringField('Name', validators=[DataRequired()])
    groups = EffectGroupListField('groups', description="Names of groups in this stack, one per line")

    submit = SubmitField('Save')

    def populate_obj(self, obj):
        obj.name = self.name.data
        obj.groups = []
        for n in nl_re.split(self.groups.data):
            n = n.strip()
            if n:
                obj.groups.append(n)
