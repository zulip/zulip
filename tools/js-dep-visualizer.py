"""
$ python ./tools/js-dep-visualizer.py
$ fdp -Tpng zulip-deps.dot -o zulip-deps.png -GK=2
"""

import os
from os import path
import re

PWD = path.dirname(path.realpath(__file__))
JS_FILES_DIR = path.abspath(path.join(PWD, '../static/js'))
JS_FILES = []
OUTPUT_FILE_PATH = path.abspath(path.join(PWD, '../zulip-deps.dot'))


modules = []
for js_file in os.listdir(JS_FILES_DIR):
    name = js_file.rstrip('.js')
    file_path = path.abspath(path.join(JS_FILES_DIR, js_file))

    if path.isfile(file_path) and js_file != '.eslintrc.json':
        modules.append(dict(
            filename=js_file,
            name=name,
            path=file_path,
            regex=re.compile('{}\.\w+'.format(name))
        ))

for module in modules:
    deps = []

    other_modules = filter(lambda x: x['name'] != module['name'], modules)

    with open(module['path']) as f:
        module_content = f.read()
        for other_module in other_modules:
            dependencies = re.findall(other_module['regex'], module_content)
            if len(dependencies) > 0:
                deps.append(other_module['name'])

    module['deps'] = deps

buffer = 'digraph G {'
for module in modules:
    if module['deps'] == []:
        break
    for dep in module['deps']:
        buffer += '{}->{};'.format(module['name'], dep)

buffer += '}'

with open(OUTPUT_FILE_PATH, 'w') as f:
    f.write(buffer)
