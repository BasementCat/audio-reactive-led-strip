import re
import random

from launchpad.colors import Color

from app import db


class Effect(db.Model):
    __tablename__ = 'effect'
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode(64), nullable=False, index=True)
    prop = db.Column(db.UnicodeText(), nullable=False)
    raw_duration = db.Column(db.UnicodeText())
    start = db.Column(db.UnicodeText(), nullable=False)
    end = db.Column(db.UnicodeText())
    done = db.Column(db.UnicodeText())

    _duration_unit_re = re.compile(r'^([\d.]+)\s*([bms])$', re.I)

    @property
    def _parsed_duration(self):
        m = self.unit_re.match(self.raw_duration)
        if not m:
            raise ValueError("Duration value is not in the correct format")
        return float(m.group(1)), m.group(2)

    def duration_to_seconds(self, bpm, bpmeasure=None):
        value, unit = self._parsed_duration
        bpmeasure = bpmeasure or 4
        if unit == 's':
            return value
        else:
            beat_len = 60 / bpm
            if unit == 'b':
                return value * beat_len
            elif unit == 'm':
                return (value * bpmeasure) * beat_len


class effect_to_effect_group(db.Model):
    __tablename__ = 'effect_to_effect_group'
    effect_id = db.Column(db.Integer(), db.ForeignKey('effect.id', onupdate='CASCADE', ondelete='RESTRICT'), primary_key=True)
    effect = db.relationship('Effect')
    effect_group_id = db.Column(db.Integer(), db.ForeignKey('effect_group.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
    effect_group = db.relationship('EffectGroup')
    lights = db.Column(db.UnicodeText(), nullable=False, default='*', server_default='*')


class EffectGroup(db.Model):
    __tablename__ =  'effect_group'
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode(64), nullable=False, index=True)
    color = db.Column(db.Unicode(16), nullable=False, default=lambda: random.choice(Color.ALL_COLORS_NAMES[1:]) + ':4', server_default='PINK:4')
    effects = db.relationship('effect_to_effect_group', cascade='all,delete-orphan')

    # For WTForms
    @property
    def raw_color(self):
        return self.color.split(':')[0] or 'OFF'

    @property
    def color_intensity(self):
        try:
            return int(self.color.split(':')[1])
        except:
            return 4

    def play(self, bpm, bpmeasure=None):
        for effect_info in self.effects:
            # color, intensity = self.color.split(':')
            lights = [effect_info.lights] if effect_info.lights == '*' else list(map(lambda v: v.strip(), effect_info.lights.split(',')))
            duration = effect_info.effect.duration_to_seconds(bpm, bpmeasure=bpmeasure)
            yield ('effect' if duration else 'state'), lights, duration, effect_info.effect


class effect_group_to_effect_stack(db.Model):
    __tablename__ = 'effect_group_to_effect_stack'
    effect_group_id = db.Column(db.Integer(), db.ForeignKey('effect_group.id', onupdate='CASCADE', ondelete='RESTRICT'), primary_key=True)
    group = db.relationship('EffectGroup')
    effect_stack_id = db.Column(db.Integer(), db.ForeignKey('effect_stack.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
    stack = db.relationship('EffectStack')
    # order = db.Column(db.Integer())


class EffectStack(db.Model):
    __tablename__ =  'effect_stack'
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode(64), nullable=False, index=True)
    # groups = db.relationship('EffectGroup', secondary=effect_group_to_effect_stack.__table__, order_by=effect_group_to_effect_stack.__table__.c.order)
    groups = db.relationship('EffectGroup', secondary=effect_group_to_effect_stack.__table__)

    def play(self, bpm, bpmeasure=None):
        for grp in self.groups:
            delay = 0
            state = {}
            effects = {}
            for type_, lights, duration, eff in grp.play(bpm, bpmeasure=bpmeasure):
                if type_ == 'state':
                    for l in lights:
                        state.setdefault(l, {})[eff.prop] = eff.start
                elif type_ == 'effect':
                    for l in lights:
                        effects.setdefault(l, []).append(eff)
                    delay = max(delay, duration)
            if state:
                yield 'state', state
            for eff in effects:
                yield 'effect', eff
            yield 'delay', delay


class Light(db.Model):
    __tablename__ = 'light'
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column(db.Unicode(64), nullable=False, index=True)
    x_pos = db.Column(db.Integer(), nullable=False)
    y_pos = db.Column(db.Integer(), nullable=False)
    color = db.Column(db.Unicode(16))
