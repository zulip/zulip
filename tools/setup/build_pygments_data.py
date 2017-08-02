#!/usr/bin/env python3

from pygments.lexers import get_all_lexers
import json
import os

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')
DATA_PATH = os.path.join(ZULIP_PATH, 'tools', 'setup', 'lang.json')
JS_PATH = os.path.join(ZULIP_PATH, 'static', 'generated', 'pygments_data.js')

with open(DATA_PATH) as f:
    langs = json.load(f)

lexers = get_all_lexers()
for lexer in lexers:
    for name in lexer[1]:
        if name not in langs:
            langs[name] = 0

template = '''var pygments_data = (function () {

var exports = {};

exports.langs = %s;

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = pygments_data;
}''' % json.dumps(langs)

with open(JS_PATH, 'w') as f:
    f.write(template)
