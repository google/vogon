#!/usr/bin/python
# vim: set fileencoding=utf-8 :

# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Web-based Vogon configuration file editor.

This utility starts a web server and opens a local web page in the user's
default browser, which contains a GUI to edit the JSON configuration file.
"""

from os import path
import sys
program_dir = path.abspath(path.dirname(__file__))
sys.path.insert(0, program_dir + '/third_party/bottle/')

import argparse
import subprocess
import platform
from bottle import get, post, request, route, run, static_file
import json

import vogon

config_file = ''

@get('/config')
def get_config():
    return static_file(config_file, root='./')

@post('/config')
def post_config():
    with open(config_file, 'w') as f:
        json.dump(request.json, f, indent=2)

@get('/preview/<index>')
def get_preview(index):
    video = vogon.generate_preview(config_file, int(index))
    return static_file(video, root='./')

@get('/')
def get_index():
    filename = 'index.html'
    return get_static(filename)

@get('/static/<filepath:path>')
def get_static(filepath):
    static_dir = program_dir + '/static/'
    return static_file(filepath, root=static_dir)

def open_browser(url):
    open_command = {
            'Linux': 'xdg-open',
            'Darwin': 'open',
            'Windows': 'start'}
    system = platform.system()
    args = open_command[system] + " '" + url + "'"
    subprocess.call(args, shell=True)

def main():
    global config_file
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", help="Configuration JSON file")
    parser.add_argument("--debug",
            help="Enable debug mode",
            action="store_true")
    args = parser.parse_args()
    config_file = args.config_file
    open_browser('http://127.0.0.1:8080/')
    run(host='127.0.0.1', port=8080, debug=args.debug)

if __name__=='__main__':
    main()

