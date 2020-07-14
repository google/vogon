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

"""Vogon: scalable customization of video campaigns.

Vogon combines a video creative, a data table and a layout specification,
generating a copy of the video creative combined with each line of the data
table according to the layout specification.

The data can contain text and images. The specification determines the timing,
position and font definitions for each piece of text and image, referencing
data fields through their names. Fixed text can also be used in the layout
specification.

The generated videos are (optionally) uploaded to a Youtube channel, and a
campaign specification file is generated to be imported in AdWords for Video,
creating geo-targeted campaigns for each of the videos.
"""


import argparse
import csv
import codecs
import datetime
import itertools
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from oauth2client.tools import argparser
from apiclient.errors import HttpError

program_dir = os.path.abspath(os.path.dirname(__file__))
stop_gen_threads = {}
running_gen_threads = {}

def stop_video_generation(project_dir):
  global stop_gen_threads, running_gen_threads
  print("cancelling video generation for %s"%project_dir)
  stop_gen_threads[project_dir] = True
  while True:
    if project_dir not in running_gen_threads or len(running_gen_threads[project_dir]) == 0:
      stop_gen_threads[project_dir] = False
      print("cancelled video generation for %s"%project_dir)
      break
    else:
      time.sleep(1)

def get_video_generation_percent(project_dir):
  global stop_gen_threads, running_gen_threads
  logs_dir = os.path.join("projects", project_dir, "logs")
  try:
    logs = list(os.listdir(logs_dir))
  except Exception as e:
    logs = []
  for log in logs:
    if log[-4:] != ".log" or log[:17] != "video_generation_":
      logs.remove(log)
  if len(logs):
    latest_log = sorted(logs)[-1]
    name = latest_log[17:-4]
    name = name.split("_")[0] + " " + name.split("_")[1].replace("-", ":")
    percent = subprocess.check_output(['tail', '-1',
                                        os.path.join(logs_dir, latest_log)])
    return name, percent
  else:
    return "--", "--"

def generate_all_video_variations(project_dir):
  global stop_gen_threads, running_gen_threads
  gen_id = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


  # setup logs
  logs_uri = os.path.join("projects", project_dir, "logs")
  if not os.path.isdir(logs_uri):
    os.mkdir(logs_uri)
  current_log_uri = os.path.join(logs_uri, "video_generation_%s.log" % gen_id)
  def logv(msg, log_type='a'):
    with open(current_log_uri, log_type) as log_file:
      if log_type == "a":
        log_file.write("\n")
      log_file.write("%s - %s!" % (msg,datetime.datetime.now()))
      log_file.close()


  try:
    # setup config
    config_uri = os.path.join("projects", project_dir, "config.json")
    config = load_config(config_uri)

    # setup feed
    data_uri = os.path.join("projects", project_dir, "feed.csv")
    data = read_csv_file(data_uri, ',')
    lines = enumerate(data)
    total_lines = len(data) + 0.0

    # clears generated videos
    output_uri = os.path.join("projects", project_dir, "output")
    shutil.rmtree(output_uri)
    os.mkdir(output_uri)

    # handle video generation threads
    logv("[STARTED]", log_type="w")
    stop_video_generation(project_dir)

    # adds thread as runnig for project
    if project_dir not in running_gen_threads:
      running_gen_threads[project_dir] = [gen_id]
    else:
      running_gen_threads[project_dir].append(gen_id)

    # creates videos
    for i, row in lines:
      if project_dir in stop_gen_threads and stop_gen_threads[project_dir]:
        raise Exception("Receive request to cancel video generation.")
      video = generate_video(config, row, (i + 1), project_dir)
      logv("[RUNNIG] \n %s of %s (%.1f%%)"% (i , total_lines,(100*i/total_lines)))
    if project_dir in running_gen_threads:
      running_gen_threads[project_dir].remove(gen_id)
    logv("[DONE]")
  except Exception as e:
    if project_dir in running_gen_threads:
      running_gen_threads[project_dir].remove(gen_id)
    logv("[FAIL] '%s'" % e)

def generate_videos(config_file, youtube_upload, preview_line, project_dir, flags):
    """Generate custom videos according to the given configuration file name.

    The configuration file (JSON) is interpreted, and the specified video input
    is combined with the data in the specified data file (CSV) to generate an
    output video for each line in the data file.
    """
    config = load_config(config_file)
    adwords = config['adwords']
    awv_csv_file = adwords['csv_file']
    campaigns = {}
    ads = {}
    targets = {}
    data = read_csv_file(config['data_file'], ',')
    if preview_line is not None:
        lines = [[(preview_line - 1), data[preview_line - 1]]]
    else:
        lines = enumerate(data)
    for i, row in lines:
        video = generate_video(config, row, (i + 1), project_dir)
        if youtube_upload:
            title = replace_vars(config['video_title'], row)
            description = replace_vars(config['video_description'], row)
            video_id = upload_to_youtube(video, title, description, flags)
            if video_id is not None:
                row['video_id'] = video_id
                campaign = replace_vars_in_dict(adwords['campaign'], row)
                campaigns[campaign['name']] = campaign
                ad = replace_vars_in_dict(adwords['ad'], row)
                ad['Campaign'] = campaign['name']
                ad['Video id'] = video_id
                ads[ad['name']] = ad
                target_list = replace_vars_in_targets(adwords['targets'], row)
                targets[campaign['name']] = target_list
    # Write AdWords CSV
    if youtube_upload:
        awv_csv = GoogleAdsEditorCsv(campaigns, ads, targets)
        awv_csv.write_to_file(awv_csv_file)

def generate_preview(config_file, preview_line, project_dir):
  """Generate a single video for preview and return its filename."""
  config = load_config(config_file)
  feed = os.path.join("projects", project_dir, config['data_file'])
  data = read_csv_file(feed, ',')
  video = generate_video(config, data[preview_line - 1], preview_line,
                         project_dir)
  return video

def generate_video(config, row, row_num, project_dir):
    row['$id'] = str(row_num)
    print()
    image_overlays = replace_vars_in_overlay(config['images'], row)
    text_overlays = replace_vars_in_overlay(config['text_lines'], row)
    complex_filters, txt_input_files = filter_strings(image_overlays, text_overlays)
    img_args = image_inputs(image_overlays, project_dir, txt_input_files)
    output_video = replace_vars(config['output_video'], row)
    output_video = os.path.join("projects", project_dir, "output", output_video)
    base_video = os.path.join("projects", project_dir, "assets", config['video'])
    if 'ffmpeg_path' in config:
        ffmpeg = config['ffmpeg_path']
        run_ffmpeg(img_args, complex_filters, base_video, output_video, executable=ffmpeg)
    else:
        run_ffmpeg(img_args, complex_filters, base_video, output_video)
    return output_video

def filter_strings(images, text_lines):
  """Generate a complex filter specification for ffmpeg.

  Arguments:
  images -- a list of image overlay objects
  text_lines -- a list of text overlay objects
  """
  complex_filters = []
  overlays = (images + text_lines)
  input_stream = '0:v'
  txt_input_files = []
  for i, ovr in enumerate(overlays):
    output_stream = None if i == (len(overlays) - 1) else ('ov_' + str(i))
    if 'image' in ovr:
      c_filter = image_and_video_filter(input_stream,
                                        (i+1),
                                        ovr['x'],
                                        ovr['y'],
                                        float(ovr['start_time']),
                                        float(ovr['end_time']),
                                        ovr.get('width', None),
                                        ovr.get('height', None),
                                        ovr['angle'],
                                        float(ovr['fade_in_duration']),
                                        float(ovr['fade_out_duration']),
                                        ovr['h_align'],
                                        output_stream
                                       )
    else:
      c_filter, i_file = text_filter(input_stream,
                                     (i+1),
                                     ovr['text'],
                                     ovr['font'],
                                     ovr['font_size'],
                                     ovr['font_color'],
                                     ovr['x'],
                                     ovr['y'],
                                     ovr['h_align'],
                                     float(ovr['start_time']),
                                     float(ovr['end_time']),
                                     float(ovr['fade_in_duration']),
                                     float(ovr['fade_out_duration']),
                                     ovr.get('angle', None),
                                     ovr.get('is_cropped_text', False),
                                     output_stream)
      txt_input_files.append(i_file)

    complex_filters.append(c_filter)
    input_stream = output_stream
  return complex_filters, txt_input_files

def run_ffmpeg(img_args, filters, input_video, output_video, executable='ffmpeg'):
    """Run the ffmpeg executable for the given input and filter spec.

    Arguments:
    img_args -- a list of '-i' input arguments for the images
    filters -- complex filter specification
    input_video -- main input video file name
    output_video -- output video file name
    """
    if input_video[0] != "/":
        input_video = os.path.join(program_dir, input_video)
    args = ([executable, '-y', '-i', input_video] + img_args +
            ['-filter_complex', ';'.join(filters), output_video])
    print(" ".join(args))
    try:
        subprocess.call(args)
    except Exception as e:
        print(e)

def image_inputs(images_and_videos, data_dir, text_tmp_images):
  """Generates a list of input arguments for ffmpeg with the given images."""
  include_cmd = []

  # adds images as video starting on overlay time and finishing on overlay end
  img_formats = ['gif', 'jpg', 'jpeg', 'png']
  for ovl in images_and_videos:
    filename = ovl['image']

    # checks if overlay is image or video
    is_img = False
    for img_fmt in img_formats:
      is_img = filename.lower().endswith(img_fmt)
      if is_img:
        break

    # treats image overlay
    if is_img:
      duration = str(float(ovl['end_time']) - float(ovl['start_time']))

      is_gif = filename.lower().endswith('.gif')
      has_fade = (float(ovl.get('fade_in_duration', 0)) +
                  float(ovl.get('fade_out_duration', 0))) > 0

      # A GIF with no fade is treated as an animated GIF should.
      # It works even if it is not animated.
      # An animated GIF cannot have fade in or out effects.
      if is_gif and not has_fade:
        include_args = ['-ignore_loop', '0']
      else:
        include_args = ['-f', 'image2', '-loop', '1']

      include_args += ['-itsoffset', str(ovl['start_time']), '-t', duration]

      # GIFs should have a special input decoder for FFMPEG.
      if is_gif:
        include_args += ['-c:v', 'gif']

      include_args += ['-i']
      include_cmd += include_args + ['projects/%s/assets/%s' % (data_dir,
                                                                filename)]

    # treats video overlays
    else:
      duration = str(float(ovl['end_time']) - float(ovl['start_time']))
      include_args = ['-itsoffset', str(ovl['start_time']), '-t', duration]
      include_args += ['-i']
      include_cmd += include_args + ['projects/%s/assets/%s' % (data_dir,
                                                                filename)]

  # adds texts as video starting and finishing on their overlay timing
  for img2 in text_tmp_images:
    duration = str(float(img2['end_time']) - float(img2['start_time']))

    include_args = ['-f', 'image2', '-loop', '1']
    include_args += ['-itsoffset', str(img2['start_time']), '-t', duration]
    include_args += ['-i']

    include_cmd += include_args + [str(img2['path'])]

  return include_cmd

def image_and_video_filter(
      input_stream, image_stream_index,
      x, y,
      t_start, t_end,
      width, height,
      angle,
      fade_in_duration, fade_out_duration,
      h_align,
      output_stream,
      is_text=False
  ):
  """Generates a ffmeg filter specification for image and video inputs.

  Args:
    input_stream: name of the input stream
    image_stream_index: index of the input image among the -i arguments
    x: horizontal position where to overlay the image on the video
    y: vertical position where to overlay the image on the video
    t_start: start time of the image's appearance
    t_end: end time of the image's appearance
    output_stream: name of the output stream
    fade_in_duration: float of representing how many seconds should fade in
    fade_out_duration: float of representing how many seconds should fade out
    h_align: horizontal align, for texts made image

  Returns:
    A string that represents an image/video filter specification, ready to be
    passed in to ffmpeg.
  """
  out_str = ('[%s]' % output_stream) if output_stream else ''
  image_str = '[%s:v]' % image_stream_index
  resize_str = '[vid_%s_resized]' % image_stream_index
  rotate_str = '[vid_%s_rotated]' % image_stream_index
  fadein_str = '[vid_%s_fadedin]' % image_stream_index
  fadeout_str = '[vid_%s_fadedout]' % image_stream_index

  if h_align == 'center':
    x = '%s-overlay_w/2' % x

  if h_align == 'right':
    x = '%s-overlay_w' % x

  if not width:
    width = '-1'
  if not height:
    height = '-1'
  if is_text:
    width = 'iw/4'
    height = 'ih/4'

  #scale image
  img = '%s format=rgba,scale=%s:%s %s;' % (image_str, width, height,resize_str)

  if angle and str(angle) != '0':
    img += '%s rotate=%s*PI/180:' % (resize_str, angle)
    img += 'ow=\'hypot(iw,ih)\':'
    img += 'oh=ow:'
    img += 'c=none'
    img += ' %s;' % rotate_str
  else:
    rotate_str = resize_str

  #adds fade in to image
  if float(fade_in_duration) > 0:
    fadein_start = t_start
    img += '%s fade=t=in:st=%s:d=%s:alpha=1 %s;' % (rotate_str,
                                                  fadein_start,
                                                    fade_in_duration,
                                                    fadein_str)
  else:
    img += '%s copy %s;' % (rotate_str, fadein_str)

  #adds fade out to image
  if float(fade_out_duration) > 0:
    fadeout_start = float(t_end) - float(fade_out_duration)
    img += '%s fade=t=out:st=%s:d=%s:alpha=1 %s;' % (fadein_str,
                                                     fadeout_start,
                                                     fade_out_duration,
                                                     fadeout_str)
  else:
    img += '%s copy %s;' % (fadein_str, fadeout_str)

  # place adds image to overall overlays
  start_at = t_start
  end_at = float(t_end)
  img += '[%s]%s overlay=%s:%s:enable=\'between(t,%s,%s)\' %s'
  img %= (input_stream, fadeout_str, x, y, start_at, end_at, out_str)

  return img

def process_screenshot(config, screenshot_time, video_path, output_path):
    """Calls ffmpeg to generate the screenshot.

    This function is the one that creates the screenshot.

    Args:
      ffmpeg_time_param: The time position to create the screenshot at in MM:SS
          format.
      video_path: The path to the video we want to generate screenshots
          for.
      output_path: The location to generate the screenshots.

    Returns:
      The full path to the generated screenshot.
    """
    ffmpeg_time = '00:' + screenshot_time
    args = [config['ffmpeg_path']]
    args += ['-i']
    args += [video_path]
    args += ['-ss']
    args += [ffmpeg_time]
    args += ['-vframes']
    args += ['1']
    args += ['-y']
    args += [output_path]
    logging.info(args)
    subprocess.call(args)
    return output_path

def get_video_duration(video_file_path):
  """Gets the length in seconds of a video.

  Args:
    video_file_path: the path to the video file

  Returns:
    A float with the video length in seconds or None if the length could not
    be calculated by ffmpeg.

  Raises:
    FFMpegExecutionError: if the ffmpeg process returns an error
  """
  #group all args and runs ffmpeg
  ffmpeg_output = self._info_from_ffmpeg(video_file_path,
                                         self.ffmpeg_executable)
  logging.info('ffmpeg ran with output:')
  logging.info(ffmpeg_output)

  duration_search = re.search('(?<=Duration: )([^,]*)', ffmpeg_output,
                              re.IGNORECASE)

  if duration_search:
    duration_string = duration_search.group(1)
    h, m, s = re.split(':', duration_string)
    return int(
        math.ceil(
            datetime.timedelta(
                hours=int(h), minutes=int(m), seconds=float(s)).total_seconds(
                )))
  else:
    return None

def text_filter(input_stream,
                image_stream_index,
                text,
                font, font_size, font_color,
                x, y,
                h_align,
                t_start, t_end,
                fade_in_duration, fade_out_duration,
                angle,
                is_cropped_text,
                output_stream):
    """Generate a ffmeg filter specification for a text overlay.

    Arguments:
    input_stream -- name of the input stream
    text -- the text to overlay on the video
    font -- the file name of the font to be used
    font_size, font_color -- font specifications
    x, y -- position where to overlay the image on the video
    h_align -- horizontal text alignment ("left" or "center")
    t_start, t_end -- start and end time of the image's appearance
    output_stream -- name of the output stream
    """

    # Write the text to a file to avoid the special character escaping mess
    text_file_name = write_to_temp_file(text)

    # If we have an angle, create an image with the text
    temp_image_name = write_temp_image(font_color,
                                       font,
                                       str(font_size),
                                       text_file_name,
                                       is_cropped_text)
    filters = image_and_video_filter(
      input_stream=input_stream,
      image_stream_index=image_stream_index,
      x=x,
      y=y,
      t_start=t_start,
      t_end=t_end,
      width=None,
      height=None,
      angle=angle,
      fade_in_duration=fade_in_duration,
      fade_out_duration=fade_out_duration,
      h_align=h_align,
      output_stream=output_stream,
      is_text=True
    )

    return filters, {
      'start_time':t_start,
      'end_time':t_end,
      'path':temp_image_name
  }

def write_to_temp_file(text):
    """Write a string to a new temporary file and return its name."""
    (fd, text_file_name) = tempfile.mkstemp(prefix='vogon_', suffix='.txt',
                                            text=True, #dir="tmp"
                                            )
    with os.fdopen(fd, 'w') as f:
        if text == "" or text is None:
            text = " "
        f.write(text)
        f.close()
    return text_file_name

def write_temp_image(t_color, t_font, t_size, text_file_name, is_cropped_text):
    """Writes a text to a temporary image with transparent background."""

    #creates temp file
    (fd, temp_file_name) = tempfile.mkstemp(prefix='vogon_', suffix='.png',
                                            #dir="tmp"
                                            )

    #setup args to construct image
    font_full = t_font + ""
    if t_font[0] != "/":
      font_full = os.path.join(program_dir, t_font)

    # imagemagik
    args = ['convert']

    # basic setup
    args += ['-background', 'transparent']
    args += ['-colorspace', 'sRGB']
    args += ['-font', "'%s'"%font_full]
    args += ['-pointsize', str(float(t_size) * 4.4)]
    #args += [ '-stroke', t_color]
    #args += ['-strokewidth', str(float(t_size) / 10)]
    args += ['-fill', "'%s'"%t_color]

    # fix for cropped texts
    if is_cropped_text:
      args += ['-size', '8000x8000']
      args += ['-gravity', 'center']
      args += ['-trim']

    # setup input and output files
    text_data = ''
    with open(text_file_name, 'r') as file:
        text_data = file.read().replace('\n', '')

    args += [('label:"%s"' % text_data)]
    args += [os.path.join(str(fd), str(temp_file_name))]
    print('#'*80)
    print('#'*80)
    print('#'*80)
    print(' '.join(args))

    # runs imagemagik
    rs = subprocess.check_output(' '.join(args), stderr=subprocess.STDOUT, shell=True)

    # return exported image
    return temp_file_name

def escape_path(path):
    """Escape Windows path slashes, colons and spaces, adding extra escape for ffmpeg."""
    return path.replace('\\','\\\\\\\\').replace(':','\\\\:').replace(' ','\\\\ ')

def load_config(config_file_name):
    """Load the JSON configuration file and return its structure."""
    try:
        with open(config_file_name, 'r') as f:
            retval = json.load(f)
            f.close()
        return retval
    except Exception as e:
        print("ERROR reading config file:")
        raise e

def test_read_csv_file():
    print(read_csv_file('sample.csv', ','))

def read_csv_file(file_name, delimiter):
    """Read a CSV file and return a list of the records in it.

    Return a list of dictionaries. The keys for each dict are taken from the
    first line of the CSV, which is considered the header.

    Arguments:
    file_name -- CSV file name
    delimiter -- character to be used as column delimiter
    """
    data = []
    with codecs.open(file_name, 'r',  errors='backslashreplace') as csv_file:
        csv_data = csv.DictReader((l.replace('\0', '') for l in csv_file))
        for line in csv_data:
            row = {}
            for field in line:
              row[field] = line[field]
            print(row)
            data.append(row)
        csv_file.close()
    return data

def test_replace_vars():
    config = load_config('sample.json')
    data = read_csv_file(config['data_file'],',')
    for row in data:
        print(replace_vars_in_overlay(config['images'], row))
        print(replace_vars_in_overlay(config['text_lines'], row))

def replace_vars_in_overlay(overlay_configs, values):
    """Replace all occurrences of variables in the configs with the values."""
    retval = []
    for o in overlay_configs:
        retval.append(replace_vars_in_dict(o, values))
    return retval

def replace_vars_in_dict(dic, values):
    row = {}
    for c_key, c_value in dic.items():
        if isinstance(c_value, str):
            row[c_key] = replace_vars(c_value, values)
        else:
            row[c_key] = c_value
    return row

def replace_vars_in_targets(targets, values):
    """Replace all occurrences of variables in the targets with the values."""
    retval = []
    for o in targets:
        retval.append(replace_vars_in_dict(o, values))
    return retval

def replace_vars(s, values):
    """Replace all occurrences of variables in the given string with values"""
    retval = s
    for v_key, v_value in values.items():
        replace = re.compile(re.escape('{{' + v_key + '}}'), re.IGNORECASE)
        if v_value is None:
            v_value = ""
        retval = re.sub(replace, v_value, retval)
        #print([v_value, retval])
    return retval

def main():
    parser = argparse.ArgumentParser(parents=[argparser])
    parser.add_argument("config_file", help="Configuration JSON file")
    parser.add_argument("--youtube_upload",
            help="Upload generated videos to YouTube",
            action="store_true")
    parser.add_argument("--project_dir",
            help="Name of project folder under 'projects' dir ",
            action="store_true")
    parser.add_argument("--preview_line",
            help="Generate only one video, for the given CSV line number",
            type=int)

    args = parser.parse_args()

    generate_videos(args.config_file, args.youtube_upload, args.preview_line,
                    args.project_dir)

if __name__=='__main__':
    main()