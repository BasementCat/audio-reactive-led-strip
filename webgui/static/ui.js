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

        this.color_set = null;
        if (array_has(light.functions, ['color']) && light.enums.color) {
            this.color_set = {};
            Object.entries(light.enums.color).forEach(v => {
                var color;
                if (/_/.test(v[0])) {
                    color = v[0].split('_');
                } else {
                    color = [v[0], v[0]];
                }
                for (var i = v[1][0]; i <= v[1][1]; i++) {
                    this.color_set[i] = color;
                }
            });
        }

        this.gobo_set = null;
        if (array_has(light.functions, ['gobo']) && light.enums.gobo) {
            this.gobo_set = {};
            Object.entries(light.enums.gobo).forEach(v => {
                var gobo, dither
                if (/^dither_/.test(v[0])) {
                    gobo = v[0].substring(7);
                    dither = true;
                } else {
                    gobo = v[0];
                    dither = false;
                }
                for (var i = v[1][0]; i <= v[1][1]; i++) {
                    this.gobo_set[i] = {'gobo': gobo, 'dither': dither};
                }
            });
        }

        this.dest = dest;

        this.effects = {};
        this.state_effects = {};

        // All the elements that make up the light
        this.gobo_img = null;
        if (this.gobo_set) {
            this.gobo_img = make_el('img', null, ['gobo']);
        }
        this.light_bulb = make_el('div', this.gobo_img, ['light_bulb']);
        this.light_head = make_el('div', this.light_bulb, ['light_head']);
        this.light_name = make_el('span', this.light.type + ' ' + this.light.name, ['light_name']);
        this.light_body = make_el('div', [this.light_head, this.light_name], ['light_body']);
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
        // TODO: gobo
        // TODO: white, uv, amber
        // TODO: speed
        // TODO: pan fine
        // TODO: tilt fine

        if (this.is_rgb) {
            var c = [this.light.state.red, this.light.state.green, this.light.state.blue].join(', ');
            this.light_bulb.style.backgroundColor = 'rgb(' + c + ')';
        } else if (this.color_set) {
            var color = this.color_set[this.light.state.color];
            this.light_bulb.style.background = 'linear-gradient(90deg, ' + color[0] + ' 0%, ' + color[0] + ' 50%, ' + color[1] + ' 50%, ' + color[1] + ' 100%)';
        }

        if (this.gobo_set) {
            var gobo = this.gobo_set[this.light.state.gobo];
            if (!gobo || gobo.gobo == 'none') {
                this.gobo_img.style.display = 'none';
            } else {
                this.gobo_img.style.display = 'block';
                this.gobo_img.src = '/static/gobos/' + gobo.gobo + '.png';
                // TODO: dither
            }
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
        this.dest && this.dest.removeChild(this.light_container);
    }
}

class Light {
    constructor(light_data) {
        this.type = light_data.type;
        this.name = light_data.name;
        this.functions = light_data.functions;
        this._state = light_data.state;
        this.speeds = light_data.speeds;
        this.enums = light_data.enums;
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

class AudioGraphOutput {
    constructor(dest) {
        this.dest = dest;
        this.container = make_el('div', null, ['audio_graph']);
        dest.appendChild(this.container);
        // TODO: get bins from server
        this.bins = 24;
        this.empty_data = [];
        for (var i = 0; i < this.bins; i++) {
            this.empty_data.push([i, 0]);
        }
        this.data = this.empty_data;
        this.plot = $.plot(this.container, [this.data, {}], {
            series: {
                lines: { show: true },
                points: { show: true },
                color: 'purple',
            },
            yaxis: {
                min: 0,
                max: 1,
            }
        });
    }

    update(data) {
        if (data) {
            this.data = [];
            for (var i = 0; i < this.bins; i++) {
                this.data.push([i, data[i]]);
            }
        } else {
            this.data = this.empty_data;
        }
        this.plot.setData([this.data]);
        this.plot.draw();
    }

    destroy() {
        this.dest.removeChild(this.container);
    }
}

var lights = {};
var table_output, audio_graph_output;


function reset_lights() {
    Object.entries(lights).forEach(v => v[1].destroy());
    lights = {};
    table_output && table_output.destroy();
    audio_graph_output && audio_graph_output.destroy();
    table_output = audio_graph_output = null;
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
        } else if (event.op == 'AUDIO') {
            if (!audio_graph_output) audio_graph_output = new AudioGraphOutput(document.body);
            audio_graph_output.update(event.state.bins);
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

    document.querySelector('#suspend').checked = d.kwargs.SUSPENDED;
});
socket.on('QUIT', function(d) {
    reset_lights();
});

document.querySelector('#suspend').addEventListener('change', function(e) {
    socket.emit('suspend', {args: [e.target.checked]});
});