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

import csv
import vogon
import logging
import yt_api
import os

def build_csv(project_id):
  error_message = None
  try:
    config_uri = os.path.join("projects", project_id, "config.json")
    config = vogon.load_config(config_uri)

    feed_uri = os.path.join("projects", project_id, "feed.csv")
    data = vogon.read_csv_file(feed_uri, ',')
    lines = enumerate(data)

    uploaded_video_list = yt_api.get_latest_uploaded_videos(project_id)
    adwords = config['adwords']
    campaigns = {}
    adgroups = {}
    ads = {}
    targets = {}
    uploaded_videos = 0
    missing_videos = 0

    for i, row in lines:
      account = vogon.replace_vars(adwords.get('Account', ''), row)

      # First, look for the video ID in the upload job log. If it's not there,
      # look for a column named 'youtube_video_id' in the feed.
      youtube_video_id = uploaded_video_list.get(str(i+1), None)
      if not youtube_video_id:
        youtube_video_id = 'MISSING'
        missing_videos += 1
      else:
        uploaded_videos += 1
      row['video_id'] = youtube_video_id

      # Set up campaigns
      campaign = vogon.replace_vars_in_dict(adwords['campaign'], row)
      campaign['Account'] = account
      campaigns[campaign['name']] = campaign

      # Set up campaign targets
      target_list = vogon.replace_vars_in_targets(adwords['targets'], row)
      campaign_targets = [t for t in target_list if t['level'] == 'Campaign']
      campaign['targets'] = target_list

      # Set up ad groups
      adgroup_name = vogon.replace_vars(campaign['Ad Group name'], row)
      adgroup = {'name': adgroup_name, 'Campaign': campaign}
      adgroups[adgroup_name] = adgroup

      # Set up ad group targets
      adgroup_targets = [t for t in target_list if t['level'] == 'Ad Group']
      adgroup['targets'] = target_list

      # Set up ads
      ad = vogon.replace_vars_in_dict(adwords['ad'], row)
      ad['Account'] = account
      ad['Campaign'] = campaign['name']
      ad['Ad Group'] = adgroup['name']
      ad['Video id'] = youtube_video_id
      ad['Video'] = youtube_video_id
      ads[ad['name']] = ad

      # Set up legacy targets for Bulk
      targets[campaign['name']] = target_list
      print(campaign['targets'])
      print(adgroup['targets'])

    # Write AdWords CSV
    awv_csv_file = os.path.join("projects", project_id, "google_ads_editor.csv")
    awv_editor_csv = GoogleAdsEditorCsv(campaigns, adgroups, ads)
    awv_editor_csv.write_to_file(awv_csv_file)
  except Exception as e:
    error_message = "%s"%e

  return (uploaded_videos, missing_videos), error_message


FILE_HEADERS = [
    'Account', 'Campaign', 'Location', 'Location ID', 'Campaign Status',
    'Campaign Type', 'Campaign subtype', 'Campaign Daily Budget',
    'Bid Strategy Type', 'Networks', 'Delivery Method', 'Ad Rotation',
    'Start date', 'End date', 'Ad group', 'Ad group type', 'Ad Group Status',
    'Max CPV', 'Max CPM', 'Ad Name', 'Status', 'Display URL', 'Final URL',
    'Final Mobile URL', 'Tracking template', 'Custom parameters', 'Labels',
    'Video ID', 'Criterion Type', 'Website', 'Audience', 'Keyword state',
    'Keyword', 'Topic', 'Gender', 'Ad Schedule', 'Age', 'Bid adjustment',
    'Bumper Ad'
]

GENDERS = ['Male', 'Female', 'Unknown']


class GoogleAdsEditorCsv():

  def __init__(self, campaigns, adgroups, ads):
    self.sections = []
    campaign_values = []
    adgroup_values = []
    campaign_target_values = []
    target_values = []
    gender_targeted_adgs = []
    adgroups_by_campaign = {}
    ad_group_base_name = 'Ad Group_%03d (%s)'
    default_ad_group_base_name = 'Default Ad Group (%s)'

    for c in campaigns.values():
      is_bumper = (c['Campaign Type'] == 'Video - Bumper ad')

      ad_rotation = c['Ad rotation']
      if ad_rotation.lower() == 'optimize for views':
        ad_rotation = 'Optimize for Clicks'
      m_bid = c['Mobile bid modifier'].strip().strip('%').strip()
      if not m_bid:
        m_bid = '0'

      values = {
          'Account': c.get('Account'),
          'Campaign': c['name'],
          'Campaign Status': c['Status'],
          'Campaign Type': c['Campaign Type'],
          'Campaign subtype': 'All features',
          'Campaign Daily Budget': c['Budget'],
          'Bid Strategy Type': ('Manual CPM' if is_bumper else 'Manual CPV'),
          'Labels': 'Vogon_Generated',
          # Use these values: YouTube Videos;YouTube Search;Display Network,
          # separated by a semicolon
          'Networks': c['Network'],
          # Use AWFE names for reference
          'Delivery Method': c['Delivery method'],
          'Start date': c['Start date'],  # YYYY-MM-DD
          'End date': c['End date'],  #YYYY-MM-DD
          'Ad Rotation': ad_rotation,  # Use AWEditor names for reference
          'Bid adjustment': m_bid
      }
      campaign_values.append(values)

      # Supported target types: Location (for campaigns), Keyword, Placement,
      # Topic, Audience
      # We can have more than one targeting per video, so iterating
      for t in c['targets']:
        # Targeting comes in two flavors: campaign and ad group (if none
        # specified, then ad group)
        target_level = t.get('level', None)
        if target_level is not None and target_level == 'Campaign':
          if t['type'] == 'Location':
            # You can concatenate targets by separating them with a semicolon.
            # Commas are not supported in locations anymore, since canonical
            # locations have commas in them, creating wrong targeting

            target_array = t['value'].split(';')

            for tgv in target_array:
              # Locations must be canonical names from
              # https://developers.google.com/adwords/api/docs/appendix/geotargeting
              tgv = tgv.strip()
              if is_intish(tgv):
                values = {
                    'Location ID': tgv,
                    'Account': c.get('Account'),
                    'Campaign': c['name']
                }
                campaign_target_values.append(values)
              else:
                values = {
                    'Location': tgv,
                    'Account': c.get('Account'),
                    'Campaign': c['name']
                }
                campaign_target_values.append(values)

          elif t['type'] == 'Ad Schedule':
            if ';' in t['value']:
              target_array = t['value'].split(';')
            else:
              target_array = t['value'].split(',')

            for tgv in target_array:
              values = {
                  'Ad Schedule': tgv,
                  'Account': c.get('Account'),
                  'Campaign': c['name']
              }
              campaign_target_values.append(values)
          else:
            raise ValueError('Invalid type for Campaign targeting.', t['type'])

    i = 1
    for ag in adgroups.values():

      c = ag['Campaign']
      # Creating the Ad group (formerly known as target group)
      adgroup_name = ag.get('name', None)
      if not adgroup_name:
        adgroup_name = ad_group_base_name % (i, c['name'])
      values = {
          'Ad group': adgroup_name,
          'Ad group type': ('Bumper' if is_bumper else 'InStream'),
          'Ad Group Status': 'enabled',
          'Campaign': c['name'],
          'Account': c.get('Account', ''),
          'Max CPV': c['Max CPV'],
          # This is not a typo, Max Bid in the UI is mapped to Max CPV in
          # the config for historical reasons we should not speculate about.
          'Max CPM': c['Max CPV'],
          'Labels': 'Vogon_Generated'
      }
      adgroup_values.append(values)

      # Putting the target groups in a dict so the ads can refer to it
      # later on. The variable is not used later, but the initialization
      # has important side effects in adgroups_by_campaign.
      campaign_adgroups = adgroups_by_campaign.setdefault(c['name'], [])
      campaign_adgroups.append(adgroup_name)

      for t in ag['targets']:
        # Targeting comes in two flavors: campaign and ad group (if none
        # specified, then ad group)
        target_level = t.get('level', None)
        if target_level is not None and target_level == 'Ad Group':
          # Supported target types for AdGroups: Keyword, Placement, Topic,
          # Audience
          # TODO: support extra target types

          # You can concatenate targets by separating them with a semicolon.
          # Commas are supported too, but only for backwards compatibility
          if ';' in t['value']:
            target_array = t['value'].split(';')
          else:
            target_array = t['value'].split(',')

          for tgv in target_array:
            if t['type'] == 'Keyword':
              if tgv.startswith('[') and tgv.endswith(']'):
                match_type = 'Exact'
              elif tgv.startswith("\"") and tgv.endswith("\""):
                match_type = 'Phrase'
              elif tgv.startswith('-'):
                match_type = 'Negative'
              else:
                match_type = 'Broad'

              # Remove special chars from keywords
              if match_type != 'Broad':
                tgv = tgv[1:-1]

              values = {
                  'Account': c.get('Account', ''),
                  'Campaign': c['name'],
                  'Ad group': adgroup_name,
                  'Max CPV': t.get('max_cpv', ''),
                  'Max CPM': t.get('max_cpv',
                                   ''),  # This is not a typo, historical
                  'Keyword state': 'enabled',
                  'Keyword': tgv,
                  'Criterion Type': match_type
              }
              target_values.append(values)
            elif t['type'] == 'Placement':
              values = {
                  'Account': c.get('Account', ''),
                  'Campaign': c['name'],
                  'Ad group': adgroup_name,
                  'Max CPV': t.get('max_cpv', ''),
                  'Max CPM': t.get('max_cpv',
                                   ''),  # This is not a typo, historical
                  # TODO: let users add negative placements
                  'Criterion Type': '',
                  'Website': tgv
              }
              target_values.append(values)
            elif t['type'] == 'Topic':
              values = {
                  'Account': c.get('Account', ''),
                  'Campaign': c['name'],
                  'Ad group': adgroup_name,
                  'Max CPV': t.get('max_cpv', ''),
                  'Max CPM': t.get('max_cpv',
                                   ''),  # This is not a typo, historical
                  # TODO: let users add negative topics
                  'Criterion Type': '',
                  'Topic': tgv
              }
              target_values.append(values)
            elif t['type'] == 'Audience':
              values = {
                  'Account': c.get('Account', ''),
                  'Campaign': c['name'],
                  'Ad group': adgroup_name,
                  'Max CPV': t.get('max_cpv', ''),
                  'Max CPM': t.get('max_cpv',
                                   ''),  # This is not a typo, historical
                  # TODO: let users add negative audiences
                  'Criterion Type': '',
                  'Audience': tgv
              }
              target_values.append(values)
            elif t['type'] == 'Gender':
              if tgv != '':
                values = {
                    'Account': c.get('Account', ''),
                    'Campaign': c['name'],
                    'Ad group': adgroup_name,
                    'Max CPV': t.get('max_cpv', ''),
                    'Max CPM': t.get('max_cpv',
                                     ''),  # This is not a typo, historical
                    # TODO: let users add negative topics
                    'Criterion Type': '',
                    'Gender': tgv
                }
                target_values.append(values)
                gender_targeted_adgs.append(adgroup_name)
            elif t['type'] == 'Age':
              if tgv != '':
                values = {
                    'Account': c.get('Account', ''),
                    'Campaign': c['name'],
                    'Ad group': adgroup_name,
                    'Max CPV': t.get('max_cpv', ''),
                    'Max CPM': t.get('max_cpv',
                                     ''),  # This is not a typo, historical
                    # TODO: let users add negative topics
                    'Criterion Type': '',
                    'Age': tgv
                }
                target_values.append(values)
            else:
              raise ValueError('Invalid type for Ad Group targeting', t['type'])

      i += 1

    # Adds ad groups for campaigns that have not created ad groups, like
    # Location only targeted campaigns.
    for c in campaigns.values():
      if c['name'] not in adgroups_by_campaign.keys():
        missing_adgroup_name = default_ad_group_base_name % c['name']
        missing_ad_group = {
            'Ad group': missing_adgroup_name,
            'Ad group type': ('Bumper' if is_bumper else 'InStream'),
            'Ad Group Status': 'enabled',
            'Campaign': c['name'],
            'Account': c.get('Account', ''),
            'Max CPV': c['Max CPV'],
            # This is not a typo, Max Bid in the UI is mapped to Max CPV in the
            # config for historical reasons we should not speculate about.
            'Max CPM': c['Max CPV'],
            'Labels': 'Vogon_Generated'
        }
        adgroup_values.append(missing_ad_group)
        adgroups_by_campaign[c['name']] = [missing_adgroup_name]

    # Adds demographic default targeting to all ad groups. AdWords Editor does
    # not add them life AWFE does
    for adg in adgroup_values:
      if adg['Ad group'] not in gender_targeted_adgs:
        for g in GENDERS:
          values = {
              'Account': adg.get('Account', ''),
              'Campaign': adg['Campaign'],
              'Ad group': adg['Ad group'],
              'Gender': g
          }
          target_values.append(values)

    self.add_section(campaign_values, 'campaign')
    self.add_section(adgroup_values, 'adgroup')
    self.add_section(target_values, 'target')
    self.add_section(campaign_target_values, 'campaign_target')
    ad_values = []

    for ad in ads.values():
      values = {
          'Account':
              ad.get('Account', ''),
          'Campaign':
              ad['Campaign'],
          'Ad group':
              ad['Ad Group'],
          'Ad Name':
              ad['name'],
          'Status':
              'enabled',
          # Only used for in-stream ads
          'Display URL':
              ad['Display Url'],
          # New Final URL field is Final Url, but we kept the Destination Url
          # for backwards compatibility.
          'Final URL': (ad['Final Url']
                        if 'Final Url' in ad else ad['Destination Url']),
          'Final Mobile URL':
              ad.get('Mobile Final Url', ''),
          'Tracking template':
              ad.get('Tracking Template', ''),
          # TODO: add ability to create custom params for tracking template
          'Custom parameters':
              '',
          'Labels':
              'Vogon_Generated',
          'Video ID':
              ad['Video id'],
          'Bumper Ad': ('[]' if is_bumper else '')
      }
      ad_values.append(values)
    self.add_section(ad_values, 'ad')

  def add_section(self, values, type):
    section = AwEditorCsvSection(values, type)
    self.sections.append(section)

  def get_csv(self):
    retval = []
    retval.append(pad_line(FILE_HEADERS))
    for s in self.sections:
      s_csv = s.get_csv()
      if s_csv is not None and len(s_csv) > 0:
        retval += s_csv
    return retval

  def write_to_file(self, file_name):
    with open(file_name, 'w') as f:
      csvwriter = csv.writer(
          f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
      csvwriter.writerows(self.get_csv())
      f.close()


class AwEditorCsvSection():

  def __init__(self, values, section_type, locale='en_US'):
    """Create a new AdWords for Video CSV section.

    Args:
      value: array of dictionaries, each dict represents one line in the CSV.
        The keys of each line will be matched with the headers on the file.
      section_type: the type of entity represented in the section, such as ad
        and campaign.
      locale: ISO 639 language code.
    """
    self.values = values
    self.section_type = section_type
    self.locale = locale

  def get_csv(self):
    retval = []
    if len(self.values) > 0:
      for line in self.values:
        line_values = []
        for header in FILE_HEADERS:
          value = line.get(header, '')
          if value is not None:
            line_values.append(value)
          else:
            line_values.append('')
            logging.warning(
                'Missing value from section %s, column %s in attempt to ' +
                'generate AdWords Editor CSV.', self.section_type, header)
        retval.append(pad_line(line_values))
    return retval


def pad_line(arr):
  return arr + ([None] * (len(FILE_HEADERS) - len(arr)))


def is_intish(str_val):
  try:
    str_val = str(str_val)
    int_val = int(''.join([c for c in str_val if c.isdigit()]))
    return (str(int_val).lstrip('0') == str_val.lstrip('0'))
  except Exception as e:
    return False
