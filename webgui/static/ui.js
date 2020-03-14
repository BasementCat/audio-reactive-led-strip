function make_el(tag, html, classes) {
    var el = document.createElement(tag);
    var add_el = function(v) {
        if (v) {
            if (typeof v === 'string')
                el.appendChild(document.createTextNode(v));
            else if (typeof v.push !== 'undefined')
                v.map(add_el);
            else
                el.appendChild(v);
        }
    }
    add_el(html);
    (classes || []).forEach(c => el.classList.add(c));
    return el;
}

function array_has(arr, items) {
    for (var i = 0; i < items.length; i++) {
        if (arr.indexOf(items[i]) < 0) return false;
    }
    return true;
}

class Output {
    constructor(light) {
        this.light = light;
    }

    monitor_event(event) {}

    render() {}

    destroy() {}
}

class TableRowOutput extends Output {
    constructor(light, fields) {
        super(light);
        this.fields = fields;
        this.tr = document.createElement('tr');
        this.tdmap = {};
        this.fields.forEach(n => {
            var td = document.createElement('td');
            this.tdmap[n] = td;
            this.tr.appendChild(td);
        });
    }

    render() {
        this.fields.forEach(n => {
            this.tdmap[n].innerHTML = this.light[n] || this.light.state[n] || '';
        });
    }
}

class TableOutput {
    constructor(dest, lights) {
        this.dest = dest;
        this.table = document.createElement('table');
        this.thead = document.createElement('thead');
        this.tbody = document.createElement('tbody');

        var headers = ['name', 'type', 'effects', 'state_effects'];
        lights.forEach(l => {
            l.functions.forEach(f => headers.indexOf(f) < 0 && headers.push(f));
        });

        headers.forEach(h => {
            var th = document.createElement('th');
            th.innerHTML = h;
            this.thead.appendChild(th);
        });

        lights.forEach(l => {
            var o = new TableRowOutput(l, headers);
            l.add_output(o);
            this.tbody.appendChild(o.tr);
        });

        this.table.appendChild(this.thead);
        this.table.appendChild(this.tbody);
        this.dest.appendChild(this.table);
    }

    destroy() {
        this.dest.removeChild(this.table);
    }
}

class MovingHeadOutput extends Output {
    constructor(dest, light) {
        super(light);
        if (light.functions.indexOf('pan') < 0) return;

        this.is_rgb = array_has(light.functions, ['red', 'green', 'blue']);

        this.dest = dest;

        this.effects = {};
        this.state_effects = {};

        // All the elements that make up the light
        this.light_bulb = make_el('div', null, ['light_bulb']);
        this.light_head = make_el('div', this.light_bulb, ['light_head']);
        this.light_body = make_el('div', this.light_head, ['light_body']);
        this.effects_list = make_el('ul', null, ['info_list', 'effects']);
        this.state_effects_list = make_el('ul', null, ['info_list', 'state_effects']);
        this.light_container = make_el('div', [this.light_body, this.state_effects_list, this.effects_list], ['light_container']);

        this.dest.appendChild(this.light_container);
    }

    _transition_duration(attr) {
        var ts = this.light.speeds[attr];
        if (!ts) return 0;
        var s = this.light.state.speed;
        return ts[0] + ((s / 255) * (ts[1] - ts[0]));
    }

    monitor_event(event) {
        var obj = this[event.op.toLowerCase() + 's'];
        if (event.op_state == 'NEW') {
            obj[event.op_name] = [event.op_name, [event.state.start, event.state.end, event.state.done].join('->'), event.state.duration].join(' ');
        } else if (event.op_state == 'DONE') {
            delete obj[event.op_name];
        }
    }

    render() {
        // TODO: fixed colors
        // TODO: gobo
        // TODO: white, uv, amber
        // TODO: speed
        // TODO: pan fine
        // TODO: tilt fine

        if (this.is_rgb) {
            var c = [this.light.state.red, this.light.state.green, this.light.state.blue].join(', ');
            this.light_bulb.style.backgroundColor = 'rgb(' + c + ')';
        }
        // TODO: do this better
        this.light_bulb.style.opacity = this.light.state.dim / 255;

        // TODO: don't assume 540
        this.light_head.style.transition = 'transform ' + this._transition_duration('pan') + 's';
        this.light_head.style.transform = 'rotate(' + ((this.light.state.pan / 255) * 540) + 'deg)';

        this.light_bulb.style.transition = 'top ' + this._transition_duration('tilt') + 's';
        this.light_bulb.style.top = ((this.light.state.tilt / 255) * 70) + '%';

        this.effects_list.innerHTML = Object.entries(this.effects).map((n, v) => '<li>' + v + '</li>');
        this.state_effects_list.innerHTML = Object.entries(this.state_effects).map((n, v) => '<li>' + v + '</li>');
    }

    destroy() {
        try {
            this.dest && this.dest.removeChild(this.light_body);
        } catch (e) {}
    }
}

class Light {
    constructor(light_data) {
        this.type = light_data.type;
        this.name = light_data.name;
        this.functions = light_data.functions;
        this._state = light_data.state;
        this.speeds = light_data.speeds;
        this.outputs = [];
    }

    add_output(out) {
        this.outputs.push(out);
    }

    set state(state) {
        for (var k in state) {
            this._state[k] = state[k];
        }
        this.outputs.forEach(o => o.render());
    }
    get state() {
        return this._state;
    }

    monitor_event(event) {
        this.outputs.forEach(o => {o.monitor_event(event); o.render();});
    }

    destroy() {
        this.outputs.forEach(o => o.destroy());
    }
}

var lights = {};
var table_output;


function reset_lights() {
    Object.entries(lights).forEach(v => v[1].destroy());
    lights = {};
    table_output && table_output.destroy();
    table_output = null;
}


var socket = io();
socket.on('connect', function() {
    reset_lights();
});
socket.on('MONITOR', function(d) {
    d.args.forEach(event => {
        if (event.op == 'STATE') {
            if (!lights[event.name]) return;
            lights[event.name].state = event.state;
        } else if (event.op == 'EFFECT' || event.op == 'STATE_EFFECT') {
            if (!lights[event.name]) return;
            lights[event.name].monitor_event(event);
        } else {
            console.log("mon %o", event);
        }
    });
});
socket.on('LIGHTS', function(d) {
    d.args.forEach(light_data => {
        var light = new Light(light_data);
        light.add_output(new MovingHeadOutput(document.body, light))
        lights[light.name] = light;
    });
    table_output = new TableOutput(document.body, Object.entries(lights).map(v => v[1]));
});
socket.on('QUIT', function(d) {
    reset_lights();
});