#!/usr/bin/python
# vim: set fileencoding=utf-8 :

# Copyright 2019 Google Inc. All rights reserved.
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
from bottle import get, post, delete, request, route, run, static_file, response
import codecs
from io import StringIO
import csv
from distutils.dir_util import copy_tree
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib
import zipfile

import vogon
import yt_api
import google_ads_editor_csv as g_ads_editor

################################################################################
# YOUTUBE AUTHENTICATION
################################################################################
@post('/api/youtube_auth/get_device_code')
def get_device_code():
  yt_status, yt_response = yt_api.get_device_code()
  response.status = yt_status
  return yt_response


@post('/api/youtube_auth/check_device_authorization')
def check_device_authorization():
  yt_status, yt_response = yt_api.check_device_authorization(request.json['code'])
  response.status = yt_status
  return yt_response


@post('/api/youtube/list_channels')
def list_channels():
  _, refresh_token_response = yt_api.refresh_access_token(request.json['refresh_token'])
  new_access_token = json.loads(refresh_token_response)['access_token']

  yt_status, yt_response = yt_api.list_channels(new_access_token)
  yt_response_content = json.loads(yt_response)

  response.status = yt_status
  yt_response_content['access_token'] = new_access_token
  yt_response_content['refresh_token'] = request.json['refresh_token']

  return yt_response_content


@post('/api/youtube/start_video_upload')
def start_video_upload():
  return yt_api.start_video_upload(request.json)


@post('/api/youtube/remove_uploaded_videos')
def remove_uploaded_videos():
  return yt_api.remove_uploaded_videos(request.json)

@get('/api/youtube/read_log/<project_id>')
def read_log(project_id):
  return yt_api.read_log(project_id, 1)


################################################################################
# CONFIG ACTIONS
################################################################################
@get('/api/projects/<project_folder>/config')
def get_config(project_folder):
  config_file = os.path.join("projects", project_folder, "config.json")
  return static_file(config_file, root='./')

@get('/api/sheets_client_id')
def get_secrest_json():
  secret_file = "credentials/oauth_2_client_secret.json"
  with open(secret_file) as s_file:
    ctn = json.loads(s_file.read())
    s_file.close()
  return json.dumps(ctn["web"]["client_id"])

@post('/api/projects/<project_folder>/config')
def post_config(project_folder):
    config_file = os.path.join("projects", project_folder, "config.json")
    with open(config_file, 'w') as f:
        json.dump(request.json, f, indent=2)
        f.close()


################################################################################
# VIDEO GENERATION ACTIONS
################################################################################
@get('/api/projects/<project_folder>/preview/row/<index>')
def generate_preview(project_folder, index):
  config_file = os.path.join("projects", project_folder, "config.json")
  video = vogon.generate_preview(config_file, int(index),
                                 project_dir=project_folder)
  return static_file(video, root='./', download=video)

@post('/api/projects/<project_id>/generate_all_videos')
def generate_all_variations(project_id):
  arg = (project_id,)
  t = threading.Thread(target=vogon.generate_all_video_variations, args=arg)
  t.start()
  return json.dumps("Started")

@get('/api/projects/<project_id>/cancel_video_generation')
def cancel_video_generation(project_id):
  vogon.stop_video_generation(project_id)
  return json.dumps("Canceled")

@get('/api/projects/<project_id>/update_on_video_generation')
def update_on_video_generation(project_id):
  started_at, current_state = vogon.get_video_generation_percent(project_id)
  current_state = current_state.decode('utf-8') if current_state != "--" else ""
  return json.dumps({
      "started_at": str(started_at),
      "current_state": current_state
  })

################################################################################
# PROJECT MANAGEMENT ACTIONS
################################################################################
@get('/api/projects/list')
def get_available_projects():
  if not os.path.exists("projects"):
    os.makedirs("projects")
  dirs = os.listdir("projects")
  output = []
  for d in dirs:
    if d[0] != ".":
      output.append({
        "name": d,
        "size": du("projects/"+d)
      })
  return json.dumps(output)

@post('/api/projects/new/name/<project_folder>')
def copy_base_project(project_folder):
  project_folder = re.sub(r'[^\w_]', '', project_folder)
  project_dir = os.path.join("projects", project_folder)
  base_dir = "base_project/"
  is_taken = os.path.isdir(project_dir)
  if not is_taken:
    # copies base project
    copy_tree(base_dir, project_dir)
    # fixes config file
    conf_file_path = os.path.join(project_dir, "config.json")
    data = ""
    with open(conf_file_path, 'r') as config_file:
      data = config_file.read().replace("{{project_id}}", project_folder)
      config_file.close()
    with open(conf_file_path, 'w') as config_file:
      config_file.write(data)
    time.sleep(2)
    # returns success
    return json.dumps({"success":True, "project": project_folder})
  else:
    return json.dumps({"success":False, "project": project_folder})

@post('/api/projects/<project_folder>/clear')
def clear_project(project_folder):
  project_folder = os.path.join("projects", project_folder, "output")
  shutil.rmtree(project_folder)
  os.mkdir(project_folder)
  return json.dumps("True")


@post('/api/projects/<project_folder>/delete')
def delete_project(project_folder):
  project_folder = os.path.join("projects", project_folder)
  shutil.rmtree(project_folder)
  return json.dumps("True")



################################################################################
# ASSETS MANAGEMENT ACTIONS
################################################################################
@get('/api/projects/<project_id>/google_ads_editor_file')
def generate_and_download_editor_file(project_id):
    (uploaded, missing),error = g_ads_editor.build_csv(project_id)
    if error is not None:
      return json.dumps({"msg": "ERROR generating CSV: %s" % error})
    elif missing >0:
      return json.dumps({
          "msg": "CSV file has %s of %s videos, please make sure to generate "
                 "all videos and upload all of them to YouTube Before "
                 "downloading the Editor CSV." % (uploaded, missing)
      })
    else:
      feed_name = "google_ads_editor.csv"
      feed_path = os.path.join("projects", project_id)
      file_path = os.path.join(feed_path, feed_name)
      filename = str(os.path.basename(file_path))

      # renders to browser as file to download, not to display.
      response.headers['Content-Type'] = 'application/octet-stream'
      response.headers['Content-Disposition'] = 'attachment; filename="%s"'
      response.headers['Content-Disposition'] %= (filename)
      return static_file(feed_name, root=feed_path, download=filename)

@post('/api/projects/<project_id>/feed_content_upload')
def feed_content_upload(project_id):
  feed_uri = "projects/%s/feed.csv" % project_id
  feed_data = json.loads(request.body.read())['feed_data']
  queue = StringIO()
  writer = csv.writer(queue, dialect=csv.excel)
  encoder = codecs.getincrementalencoder('utf-8')()
  with open(feed_uri,'wb') as feed_file:
    for feed_row in feed_data:
      writer.writerow([v for v in feed_row])
      data = queue.getvalue()
      feed_file.write(encoder.encode(data))
      queue.truncate(0)
    feed_file.close()
  return json.dumps({'success': True})

@get('/api/projects/<project_id>/fonts')
def get_font_list(project_id):
  matches = []
  font_dirs = []
  font_dirs.append("projects/%s/assets" % project_id)
  font_dirs.append("/Library/Fonts")
  font_dirs.append("/System/Library/Fonts")
  font_dirs.append("/usr/share/fonts")
  font_dirs.append("~/fonts")
  font_dirs.append("~/.fonts")
  for font_dir in font_dirs:
    try:
      for root, dirnames, filenames in os.walk(font_dir):
        for filename in filenames:
          font_file = os.path.join(root, filename)
          if filename[-4:] in (".ttf",".otf"):
            beaut_name = filename[:-4].replace("_"," ").replace("-"," ")
            beaut_name = " ".join(re.findall('[A-Z][^A-Z]*', beaut_name))
            if not beaut_name:
              beaut_name = filename[:-4].replace("_"," ").replace("-"," ").split(" ")
              beaut_name = " ".join([w.capitalize() for w in beaut_name])
            matches.append([beaut_name, font_file])
    except Exception as e:
      print("error loading fonts: "+e)
  return json.dumps(sorted(matches))

@get('/api/projects/<project_id>/assets')
def get_assets_list(project_id):
  assets_path = "projects/%s/assets" % project_id
  matches = []
  for root, dirnames, filenames in os.walk(assets_path):
    for filename in filenames:
      asset = os.path.join(root, filename)
      asset = asset.replace(assets_path, '')[1:]
      matches.append(asset)
  return json.dumps(sorted(matches))

@post('/api/projects/<project_id>/assets')
def post_single_asset(project_id):
  assets_path = "projects/%s/assets/" % project_id
  with PostedFileWriter(request) as file_path:
    if file_path[-4:] == '.zip':
      with zipfile.ZipFile(file_path, 'r') as f:
        f.extractall(assets_path)
    else:
      _, asset_name = os.path.split(file_path)
      new_asset_path = assets_path + asset_name
      shutil.copy(file_path, new_asset_path)
    return get_assets_list(project_id)

def move_file(origin_path, dest_path):
    upload = bottle.request.files.get('file')
    upload.save(dest_path)
    return 1
    with open(origin_path, 'r') as of:
        with open(dest_path, 'w') as df:
          df.write(of.read())
          df.close()
          of.close()

@delete('/api/projects/<project_id>/assets/')
def delete_asset(project_id):
  asset_name = request.query['asset_path']
  try:
    assets_path = "projects/%s/assets/" % project_id
    asset_full_path = os.path.join(assets_path, asset_name)
    os.unlink(asset_full_path)
  except Exception as e:  # pylint: disable=broad-except
    error_msg = 'Error unlinking file %s.\nError: %s.'
    error_msg %= (request.body, e)
    print(error_msg)
  return get_assets_list(project_id)

@get('/api/projects/<project_id>/download/assets/')
def download_asset(project_id):
  asset_name = request.query['asset_path']
  assets_path = "projects/%s/assets/" % project_id
  file_path = os.path.join(assets_path, asset_name)
  filename = str(os.path.basename(file_path))

  # renders to browser as file to download, not to display.
  response.headers['Content-Type'] = 'application/octet-stream'
  response.headers['Content-Disposition'] = 'attachment; filename="%s"'
  response.headers['Content-Disposition'] %= (filename)
  return static_file(asset_name, root=assets_path, download=filename)


################################################################################
# Main page Actions
################################################################################
@get('/#!/project/<project_folder>')
def get_index(project_folder):
    filename = 'html/index.html'
    return get_static(filename)

@get('/')
def get_index():
    filename = 'html/index.html'
    return get_static(filename)


################################################################################
# Static Files
################################################################################
@get('/static/<filepath:path>')
def get_static(filepath):
    static_dir = program_dir + '/static/'
    return static_file(filepath, root=static_dir)


################################################################################
# Helpers
################################################################################

def du(path):
  """disk usage in human readable format (e.g. '2,1GB')"""
  return subprocess.check_output(['du','-sh', path]).split()[0].decode('utf-8')

class PostedFileWriter(object):
  """Defines a resource to use on 'with' statements to clean up after upload."""
  # not used
  def __init__(self, request):
    self.request = request
  # not used
  def __enter__(self):
    self.temp_dir = tempfile.mkdtemp()
    # ngFileUpload sends the content in the "file" parameter by default
    input_file = request.files.get("file")
    if input_file.filename:
      file_name = input_file.filename
      file_path = os.path.join(self.temp_dir, file_name)
      buffer_size = 2**16  # 65k
      with open(file_path, 'wb') as output_file:
        buf = input_file.file.read(buffer_size)
        while buf:
          output_file.write(buf)
          buf = input_file.file.read(buffer_size)
        output_file.close()
      return file_path
    else:
      return None
  # not used
  def __exit__(self, type_, value, traceback_):
    shutil.rmtree(self.temp_dir)


################################################################################
# Main
################################################################################

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug",
            help="Enable debug mode",
            action="store_true")
    args = parser.parse_args()
    run(host='0.0.0.0', port=8080, debug=args.debug)

if __name__=='__main__':
    main()
