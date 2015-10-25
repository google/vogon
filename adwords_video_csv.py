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

FIRST_LINE = ["Ad Report"]

FILE_HEADERS = [
                "Campaign",
                "Location",
                "Campaign state",
                "Campaign type",
                "Campaign subtype",
                "Budget",
                "Bid Strategy Type",
                "Networks",
                "Delivery Method",
                "Ad Rotation",
                "Start date",
                "End date",
                "Ad group",
                "Ad group type",
                "Ad group state",
                "Max. CPV",
                "Ad",
                "Ad state",
                "Description line 1",
                "Description line 2",
                "Display URL",
                "Final URL",
                "Mobile final URL",
                "Tracking template",
                "Custom parameter",
                "Video Thumbnail",
                "YouTube Destination Page",
                "Labels",
                "Video",
                "Is negative",
                "Placement state",
                "Placement",
                "Audience state",
                "Audience",
                "Keyword state",
                "Keyword",
                "Match type",
                "Topic state",
                "Topic"
                ]
CSV_COLUMNS = 34


class AwvCsv():
    def __init__(self, campaigns, ads, targets):
        self.sections = []
        campaign_values = []
        targeting_group_values = []
        campaign_target_values = []
        target_values = []
        targeting_groups_by_campaign = {}

        for c in campaigns.values():
            values = {
                'Campaign': c['name'],
                'Campaign state': c['Status'],
                'Campaign type': "Video",
                'Campaign subtype': "All features",
                'Budget': c['Budget'],
                'Bid Strategy Type': "cpv", # TODO: let users choose the bid strategy
                'Labels': "Vogon", #TODO: let users choose labels (when AdWords lets them too
                'Networks': c['Network'], # Use these values: YouTube Videos;YouTube Search;Display Network, separated by a semicolon
                'Delivery Method': c['Delivery method'], # Use AWFE names for reference
                'Start date': c['Start date'], # YYYY-MM-DD
                'End date': c['End date'], #YYYY-MM-DD
                'Ad Rotation': c['Ad rotation'] # Use AWFE names for reference
                }
            campaign_values.append(values)

            # Supported target types: Location (for campaigns), Keyword, Placement, Topic, Audience
            # TODO: support extra target types
            # We can have more than one targeting per video, so iterating
            i = 1;
            location_count = 0
            for t in targets[c['name']]:
                # Targeting comes in two flavors: campaign and ad group (if none specified, then ad group)
                target_level = t.get('level', None)
                if target_level is not None and target_level == 'Campaign':
                    if t['type'] == "Location":
                        # You can concatenate targets by separating them with a comma
                        target_array = t['value'].split(",")
                        for tgv in target_array:
                            values = {
                                    'Campaign': c['name'],
                                    'Location': tgv # Locations must be IDs from https://developers.google.com/adwords/api/docs/appendix/geotargeting
                                }
                            # The first location must go to the campaign line
                            if location_count == 0:
                                generated_campaign = next(found for found in campaign_values if found['Campaign'] == c['name'])
                                generated_campaign['Location'] = values['Location']
                            else:
                                campaign_target_values.append(values)
                            location_count = location_count + 1
                    else:
                        raise ValueError("Invalid type for Campaign targeting.", t['type'])
                else:
                    # Creating the Ad group (formerly known as target group)
                    targeting_group_name = "Ad Group_%03d (%s)" % (i, c['name'])
                    values = {
                        'Ad group': targeting_group_name,
                        'Ad group type': "In-stream", # Must be one of In-stream or In-display TODO: let the user decide
                        'Ad group state': "enabled",
                        'Campaign': c['name'],
                        'Max. CPV': c['Max CPV'],
                        'Labels': "Vogon" #TODO: let users choose labels (when AdWords lets them too)
                    }
                    targeting_group_values.append(values)

                    # Putting the target groups in a dict so the ads can refer to it later on
                    campaign_targeting_groups = targeting_groups_by_campaign.setdefault(c['name'], [])
                    campaign_targeting_groups.append(targeting_group_name)

                    # Supported target types for AdGroups: Keyword, Placement, Topic, Audience
                    # TODO: support extra target types

                    # You can concatenate targets by separating them with a comma
                    target_array = t['value'].split(",")
                    for tgv in target_array:
                        if t['type'] == "Keyword":
                            if tgv.startswith("[") and tgv.endswith("]"):
                                match_type = "Exact"
                            elif tgv.startswith("\"") and tgv.endswith("\""):
                                match_type = "Phrase"
                            else:
                                match_type = "Broad"

                            # Remove special chars from keywords
                            if match_type != "Broad":
                                tgv = tgv[1:-1]

                            values = {
                                    'Campaign': c['name'],
                                    'Ad group': targeting_group_name,
                                    'Keyword state': "enabled",
                                    'Keyword': tgv,
                                    'Match type': match_type
                                    }
                            target_values.append(values)
                        elif t['type'] == "Placement":
                            values = {
                                    'Campaign': c['name'],
                                    'Ad group': targeting_group_name,
                                    'Is negative': "false", # TODO let users add negative placements
                                    'Placement state': "enabled",
                                    'Placement': tgv
                                    }
                            target_values.append(values)
                        elif t['type'] == "Topic":
                            values = {
                                    'Campaign': c['name'],
                                    'Ad group': targeting_group_name,
                                    'Is negative': "false", # TODO let users add negative placements
                                    'Topic state': "enabled",
                                    'Topic': tgv
                                    }
                            target_values.append(values)
                        elif t['type'] == "Audience":
                            values = {
                                    'Campaign': c['name'],
                                    'Ad group': targeting_group_name,
                                    'Is negative': "false", # TODO let users add negative placements
                                    'Audience state': "enabled",
                                    'Audience': tgv
                                    }
                            target_values.append(values)
                        else:
                            raise ValueError("Invalid type for Ad Group targeting", t['type'])

                    i += 1
        self.add_section(campaign_values, 'campaign')
        self.add_section(campaign_target_values, 'campaign_target')
        self.add_section(targeting_group_values, 'targeting_group')
        self.add_section(target_values, 'target')

        ad_values = []
        for ad in ads.values():
            # One copy of the Ad will be created for each Ad Group on its targeting
            for ad_group_for_ad in targeting_groups_by_campaign[ad['Campaign']]:

                values = {
                    'Campaign': ad['Campaign'],
                    'Ad group': ad_group_for_ad,
                    # TODO change ad['name'] to ad['name'] + '-' + ad['Headline'] for in-display ads
                    'Ad': ad['name'], # For in-display Ads, add a dash and the Headline at the end of this field
                    'Ad state': "enabled",
                    'Display URL': ad['Display Url'], # Only used for in-stream ads
                    'Final URL': ad['Destination Url'], # TODO change this to Final URL in the UI
                    'Mobile final URL': "", # TODO add ability to create a mobile final URL
                    'Tracking template': "", # TODO add ability to create a tracking template
                    'Custom parameter': "", # TODO add ability to create custom params for tracking template
                    'Video Thumbnail': ad['Thumbnail'],
                    # TODO add ad['YouTube destination'] as the value for in-display ads
                    'YouTube Destination Page': "", # Used for in-display Ads instead of URLs
                    'Labels': "Vogon", #TODO: let users choose labels (when AdWords lets them too)
                    'Video': ad['Video id'],
                    # TODO add ad['Description line one'] as the value for in-display ads
                    'Description line 1': "", # Used only for in-display ads
                    # TODO add ad['Description line two'] as the value for in-display ads
                    'Description line 2': ""# Used only for in-display ads
                    }
                ad_values.append(values)
        self.add_section(ad_values, 'ad')

    def add_section(self, values, type):
        section = AwvCsvSection(values, type)
        self.sections.append(section)

    def get_csv(self):
        retval = []
        retval.append(pad_line(FIRST_LINE))
        retval.append(pad_line(FILE_HEADERS))
        for s in self.sections:
            s_csv = s.get_csv()
            if s_csv is not None and len(s_csv) > 0:
                retval += s_csv
        return retval

    def write_to_file(self, file_name):
        with open(file_name, 'w') as f:
            csvwriter = csv.writer(
                    f, delimiter=',', quotechar='"',
                    quoting=csv.QUOTE_MINIMAL)
            csvwriter.writerows(self.get_csv())

class AwvCsvSection():
    def __init__(self, values, section_type, locale='en_US'):
        """Create a new AdWords for Video CSV section.

        Arguments:
        values -- array of dictionaries, each dict represents one line in the CSV. the
                  keys of each line will be matched with the headers on the file.
        section_type -- the type of entity represented in the section, such as ad and
                        campaign.
        locale -- ISO 639 language code.
        """
        self.values = values
        self.section_type = section_type
        self.locale = locale

    def get_csv(self):
        retval = []
        if len(self.values) > 0:
            for line in self.values:
                retval.append(pad_line([line.get(header, "").encode('utf-8') for header in FILE_HEADERS]))
        return retval

def pad_line(arr):
    return arr + ([None] * (CSV_COLUMNS - len(arr)))

