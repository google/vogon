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

SECTION_TYPE_HEADERS = {
        'campaign': "Input campaigns here",
        'ad': "Input ads here",
        'targeting_group': "Input targeting groups here",
        'campaign_target': "Input targets here (campaign settings)",
        'target': "Input targets here"
        }
CSV_COLUMNS = 15

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
                'Action': "Add",
                'Status': c['Status'],
                'Campaign': c['name'],
                'Budget': c['Budget'],
                'Budget ID': "#n/a",
                'Network': c['Network'],
                'Delivery method': c['Delivery method'],
                'Start date': c['Start date'],
                'End date': c['End date'],
                'Ad rotation': c['Ad rotation'],
                'Frequency cap': c['Frequency cap'],
                'Mobile bid modifier': c['Mobile bid modifier']
                }
            campaign_values.append(values)
            
            # Target types here: https://support.google.com/adwords/answer/3344649?hl=en
            # We can have more than one targeting per video, so iterating
            i = 1;
            for t in targets[c['name']]:
                istring = "%03d" % i
                
                # Creating the target group
                targeting_group_name = c['name'] + " Targeting Group_" + istring
                values = {
                    'Action': "Add",
                    'Status': c['Status'],
                    'Targeting group': targeting_group_name,
                    'Campaign': c['name'],
                    'Max CPV': c['Max CPV']
                    }
                targeting_group_values.append(values)
                
                # Putting the target groups in a dict so the ads can refer to it later on
                campaign_targeting_groups = targeting_groups_by_campaign.setdefault(c['name'], [])
                campaign_targeting_groups.append(targeting_group_name)
                
                # Targeting comes in two flavors: campaign and target group (if none specified, then target group)
                target_level = t.get('level', None)
                
                # You can concatenate targets by separating them with a comma
                target_array = t['value'].split(",")
                for tgv in target_array:
                    if target_level is not None and target_level == 'Campaign':
                        values = {
                            'Action': "Add",
                            'Type': t['type'],
                            'Campaign target': tgv,
                            'Campaign': c['name']
                            }
                        campaign_target_values.append(values)
                    else:
                        values = {
                            'Action': "Add",
                            'Type': t['type'],
                            'Status': 'Enabled',
                            'Target': tgv,
                            'Targeting group': targeting_group_name,
                            'Max CPV' : t.get('max_cpv', '#n/a')
                            }
                        target_values.append(values)
                i += 1
        self.add_section(campaign_values, 'campaign')
        self.add_section(targeting_group_values, 'targeting_group')
        self.add_section(campaign_target_values, 'campaign_target')
        self.add_section(target_values, 'target')

        ad_values = []
        for ad in ads.values():
            
            target_groups_for_this_ad = ", ".join(targeting_groups_by_campaign[ad['Campaign']])
            
            values = {
                'Action': "Add",
                'Status': campaigns.values()[0]['Status'],
                'Ad': ad['name'],
                'Video id': ad['Video id'],
                'Thumbnail': ad['Thumbnail'],
                'Headline': ad['Headline'],
                'Description line one': ad['Description line one'],
                'Description line two': ad['Description line two'],
                'Display Url': ad['Display Url'],
                'Destination Url': ad['Destination Url'],
                'YouTube destination': ad['YouTube destination'],
                'Showing on': ad['Showing on'],
                'Companion banner': ad['Companion banner'],
                'Enable ad for': target_groups_for_this_ad,
                'Campaign': ad['Campaign']
                }
            ad_values.append(values)
        self.add_section(ad_values, 'ad')

    def add_section(self, values, type):
        section = AwvCsvSection(values, type)
        self.sections.append(section)

    def get_csv(self):
        retval = []
        for s in self.sections:
            s_csv = s.get_csv()
            if s_csv is not None and len(s_csv) > 0:
                retval += s_csv
                for i in range(0, 2):
                    retval.append(pad_line([]))
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
                  keys of the first values are used for column headers.
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
            retval.append(pad_line([SECTION_TYPE_HEADERS[self.section_type],
                    "locale=%s" % (self.locale)]))
            column_header = self.values[0].keys()
            retval.append(pad_line([c.encode('utf-8') for c in column_header]))
            for line in self.values:
                retval.append(pad_line([c.encode('utf-8') for c in line.values()]))
        return retval

def pad_line(arr):
    return arr + ([None] * (CSV_COLUMNS - len(arr)))

