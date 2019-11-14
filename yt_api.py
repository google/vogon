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

import codecs
import csv
import datetime
import glob
import glob
import http.client
import json
import os
import re
import subprocess
import sys
import traceback
import tracemalloc
import threading
import vogon
from oauth2client.service_account import ServiceAccountCredentials

from third_party.retry import retry

HTTPS_PORT_NUMBER = 443


def get_latest_uploaded_videos(project_dir):
  # gets latest video upload file
  yt_logs_dir = os.path.join("projects", project_dir, "youtube", "*.txt")
  list_of_files = glob.glob(yt_logs_dir)
  if not list_of_files:
    return []
  latest_file = max(list_of_files, key=os.path.getctime)

  # extracts videos from file
  content = ""
  with open(latest_file,'r') as f:
    content = f.readlines()
    f.close()
  videos = {}
  for row in content:
    if len(row.split(",")) != 2:
      continue
    row_number = row.split(",")[0]
    row_number = row_number.replace("output_video_row_","").replace(".mp4","")
    yt_id = row.split(",")[1]
    videos[row_number] = yt_id.replace("\n","")

  # returns videos dict
  return videos

def read_credentials():
    f = open('credentials/webserver_client_secret.json', 'r')
    credentials = json.loads(f.read())
    f.close()
    return credentials


def get_device_code():
  credentials = read_credentials()
  data = {
    'client_id': credentials['installed']['client_id'],
    'scope': 'https://www.googleapis.com/auth/youtube'
  }

  http_client = http.client.HTTPSConnection('accounts.google.com',
                                            HTTPS_PORT_NUMBER)

  http_client.request('POST', '/o/oauth2/device/code', body=json.dumps(data))
  response = http_client.getresponse()
  response_status = response.status
  response_content = response.read()
  http_client.close()
  return response_status, response_content


def check_device_authorization(device_code):
  credentials = read_credentials()
  data = {
    'client_id': credentials['installed']['client_id'],
    'client_secret': credentials['installed']['client_secret'],
    'code': device_code,
    'grant_type': 'http://oauth.net/grant_type/device/1.0'
  }

  http_client = http.client.HTTPSConnection('www.googleapis.com',
                                            HTTPS_PORT_NUMBER)

  http_client.request('POST', '/oauth2/v4/token', body=json.dumps(data))

  response = http_client.getresponse()
  response_status = response.status
  response_content = response.read()
  http_client.close()
  return response_status, response_content


def refresh_access_token(refresh_token):
  credentials = read_credentials()
  data = {
    'client_id': credentials['installed']['client_id'],
    'client_secret': credentials['installed']['client_secret'],
    'refresh_token': refresh_token,
    'grant_type': 'refresh_token'
  }

  http_client = http.client.HTTPSConnection('www.googleapis.com',
                                            HTTPS_PORT_NUMBER)

  http_client.request('POST', '/oauth2/v4/token', body=json.dumps(data))
  response = http_client.getresponse()
  response_status = response.status
  response_content = response.read()
  http_client.close()
  return response_status, response_content


def list_channels(access_token):
    headers = {
        'Authorization': ('Bearer %s' % access_token)
    }

    http_client = http.client.HTTPSConnection('www.googleapis.com',
                                              HTTPS_PORT_NUMBER)
    http_client.request('GET', '/youtube/v3/channels?mine=true&part=snippet',
                        headers=headers)
    response = http_client.getresponse()
    response_status = response.status
    response_content = response.read()
    http_client.close()
    return response_status, response_content


def start_video_upload(request_json):
  thread_args = (
    request_json['refresh_token'],
    request_json['project_id'],
    request_json['title'],
    request_json['description'],
    request_json['channel_id'],)

  thread = threading.Thread(target=upload_videos, args=thread_args)
  thread.start()


def upload_videos(refresh_token,
                  project_id,
                  title_template,
                  description_template,
                  channel_id):
  gen_id = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

  try:
    config = vogon.load_config('projects/{}/config.json'.format(project_id))

    with codecs.open('projects/{}/feed.csv'.format(project_id), 'r',  errors='backslashreplace') as feed:
      reader = csv.DictReader((l.replace('\0', '') for l in feed))
      for row_number, row in enumerate(reader, start=1):

        video_path = 'projects/{}/output/output_video_row_{}.mp4'.format(
            project_id, row_number)

        title = vogon.replace_vars(config['video_title'], row)
        description = vogon.replace_vars(config['video_description'], row)

        write_log('[RUNNING]', 'Refreshing token', project_id, gen_id)
        _,refresh_token_response = refresh_access_token(refresh_token)
        new_access_token = json.loads(refresh_token_response)['access_token']
        write_log('[RUNNING]', 'Token refreshed', project_id, gen_id)
        write_log('[RUNNING]', 'Uploading video %s' % video_path,
                  project_id,
                  gen_id)
        video_resource = upload_video(new_access_token,
                                      gen_id,
                                      video_path,
                                      project_id,
                                      channel_id)

        write_log('[RUNNING]',
                  ('Video %s uploaded. YT video ID is '
                   '%s' % (video_path, video_resource['id'])),
                  project_id,
                  gen_id)
        write_log('[RUNNING]',
                  'Writing metadata for video %s' % video_path,
                  project_id,
                  gen_id)
        write_video_metadata(new_access_token,
                             video_resource,
                             title,
                             description)
        write_log('[RUNNING]', 'Metadata written', project_id, gen_id)
      feed.close()
    write_log('[DONE]', 'All videos uploaded!', project_id, gen_id)
  except Exception as e:
    write_log('[ERROR]', 'An error occurred - %s' % e, project_id, gen_id)


def upload_video(access_token, gen_id, filepath, project_id, channel_id):
  headers = {
    'Authorization': ('Bearer %s' % access_token),
    'Content-Type': 'application/octet-stream'
  }

  video_file = open(filepath, 'rb')

  http_client = http.client.HTTPSConnection('www.googleapis.com',
                                            HTTPS_PORT_NUMBER)
  http_client.request('POST', '/upload/youtube/v3/videos?part=snippet',
                      headers=headers,
                      body=video_file)
  yt_response = http_client.getresponse()
  video_resource = json.loads(yt_response.read())
  http_client.close()
  video_file.close()
  if yt_response.status == 200:
    persist_uploaded_video_resource(os.path.basename(filepath),
                                    gen_id,
                                    video_resource,
                                    project_id,
                                    channel_id)
  return video_resource

@retry(Exception, retries=10)
def write_video_metadata(access_token, video_resource, title, description):
  headers = {
    'Authorization': ('Bearer %s' % access_token),
    'Content-Type': 'application/json'
  }

  body = json.dumps({
    'id': video_resource['id'],
    'status': {
      'privacyStatus': 'unlisted'
    },
    'snippet': {
      'title': title,
      'categoryId': '22',
      'description': description
    }
  })

  http_client = http.client.HTTPSConnection('www.googleapis.com',
                                            HTTPS_PORT_NUMBER)
  http_client.request('PUT', '/youtube/v3/videos?part=snippet,status',
                      headers=headers, body=body)

  yt_response = http_client.getresponse()
  rs = json.loads(yt_response.read())
  if 'error' in rs and "errors" in rs['error'] and len(rs['error']['errors']):
      error = rs['error']['errors'][0]
      msg = "%s - %s"%(error["reason"], error["message"])
      http_client.close()
      raise Exception("Error uploading video: %s" % msg)
  print(rs)
  http_client.close()


def persist_uploaded_video_resource(filename,
                                    gen_id,
                                    video_resource,
                                    project_id,
                                    channel_id):
  dir_path = 'projects/{project_id}/youtube/'.format(project_id=project_id)

  if not os.path.exists(dir_path):
    os.makedirs(dir_path)
    break_line = ""
  else:
    break_line = "\n"

  file_path = '{dir_path}/{channel_id}_{gen_id}.txt'.format(
    dir_path=dir_path,
    channel_id=channel_id,
    gen_id=gen_id)

  uploaded_videos_file = open(file_path, 'a')
  uploaded_videos_file.write('{}{},{}'.format(break_line,
                                              filename,
                                              video_resource['id']))
  uploaded_videos_file.close()


def remove_uploaded_videos(request_json):

  gen_id = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
  refresh_token = request_json['refresh_token']
  project_id = request_json['project_id']
  channel_id = request_json['channel_id']

  write_log('[STARTED]', 'Removing videos', project_id, gen_id)

  pathname = 'projects/{project_id}/youtube/{channel_id}_*.txt'.format(
    project_id=project_id,
    channel_id=channel_id
  )

  uploaded_videos_file_paths = glob.glob(pathname)

  error_occurred = False

  for uploaded_video_file_path in uploaded_videos_file_paths:
    reader = open(uploaded_video_file_path, 'r')
    lines = reader.readlines()
    reader.close()

    for line in lines:
      if len(line.split(',')) > 1:
        yt_video_id = line.split(',')[1]
        write_log('[RUNNING]',
                  'Removing video {}'.format(yt_video_id),
                  project_id,
                  gen_id)

        _,refresh_token_response = refresh_access_token(refresh_token)
        new_access_token = json.loads(refresh_token_response)['access_token']
        yt_status, yt_response = remove_video(new_access_token, yt_video_id)

        # checks is video was available
        video_found = True
        rs = ''
        if yt_response and yt_response != 'None':
            rs = json.loads(yt_response)
            if 'error' in rs and 'errors' in rs['error']:
              reasons = [r['reason'] for r in rs['error']['errors']]
              print("REASONS: %s"%reasons)
              if 'videoNotFound' in reasons:
                video_found = False

        if yt_status != 204 and video_found:
          log_message = 'Error when removing video {} - {}'.format(
              yt_video_id, rs)
          write_log('[ERROR]', log_message, project_id, gen_id)


          error_occurred = True
          break

    if not error_occurred:
      os.remove(uploaded_video_file_path)

  if not error_occurred:
    write_log('[Done]',
            'All videos removed!',
            project_id,
            gen_id)


def remove_video(access_token, video_id):
  headers = {
    'Authorization': ('Bearer %s' % access_token)
  }
  video_id = video_id.replace("\n","")
  video_uri = '/youtube/v3/videos?id={}'.format(video_id)
  print(video_uri)
  http_client = http.client.HTTPSConnection('www.googleapis.com',
                                            HTTPS_PORT_NUMBER)

  http_client.request('DELETE', video_uri, headers=headers)
  response = http_client.getresponse()
  response_status = response.status
  response_content = response.read()
  http_client.close()
  return response_status, response_content


def write_log(status, message, project_id, gen_id):
  log_filepath = 'projects/{project_id}/youtube/{gen_id}.log'.format(
    project_id=project_id,
    gen_id=gen_id
  )

  dir_path = os.path.dirname(log_filepath)

  if not os.path.exists(dir_path):
    os.makedirs(dir_path)

  log_file = open(log_filepath, 'a+')
  msg = '{status} - [{datetime}]: {message}\n'.format(
    status=status,
    datetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    message=message.replace('\n', ''))
  log_file.write(msg)
  log_file.close()
  if msg[:4] == "[ERR":
      print(msg)
      print(sys.exc_info())
      traceback.print_exc(limit=10, file=sys.stdout)


def read_log(project_id, lines):
  log_files = glob.glob('projects/{}/youtube/*.log'.format(project_id))
  log_files.sort(reverse=True)

  if log_files:
    return subprocess.check_output(['tail', '-%s' % lines, log_files[0]])
  return 'No log files found'
