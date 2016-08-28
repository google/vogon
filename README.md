## Vogon: scalable customization of video campaigns

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

This is not an official Google product.

### Dependencies

In order to run Vogon, you need to have the following installed first:

* Python 2.7.x (not 3.X): https://www.python.org/download/
  * For Windows: on the second step of the wizard, check the "Add python.exe to Path" option
* FFmpeg:
  * For Mac and Linux, go to [this page](https://ffmpeg.org/download.html), but **don't click the big green button**. Instead, click on the icon for your OS below it.
  * For Windows, download from [this page](http://ffmpeg.zeranoe.com/builds/), and look for the "32-bit static" build
  * Instructions [here](http://www.wikihow.com/Install-FFmpeg-on-Windows)
* ImageMagick:
  * This package is optional, and only used if you need to render text at an angle
  * Go to [this page](http://www.imagemagick.org/script/binary-releases.php) and look for the version that is suited to your operating system and follow the instructions.
  * Make sure the command `convert` is on your path by typing `convert` on a terminal window.
* To make it easier to install the following modules, it's recommended to install PIP: https://pip.pypa.io/en/latest/installing.html 
* Google API Python client library: https://github.com/google/google-api-python-client
* Python OAuth2 library (included with google-api-python-client): https://github.com/google/oauth2client

### Preparation

Vogon can upload videos to Youtube using the Youtube API and help you create AdWords for Video campaigns. In order to do that, you need to complete the steps below.

0. Create a project in the [Google Developers Console](https://console.developers.google.com/project)
  0. In the Console, create a new project with the "Create Project" button
  0. Click "Enable an API" and activate the "Youtube Data V3" API
  0. In "APIs and Auth -> Credentials", create a new Client ID for a installed application
  0. Download the JSON file with the "Download JSON" button, and save it in the directory where you will run Vogon (together with your configuration, data and image files)
  0. The account that manages the Youtube channel and the AdWords account must both have Edit access to the project, which can be configured in the "Permissions" section of the Console
0. The Youtube and AdWords accounts must be linked - [see instructions](https://support.google.com/youtube/answer/3063482)

### Configuration

Vogon configuration files are [JSON documents](http://json.org/). Two samples are included with the source, a version for [Unix-like systems](https://github.com/googleads/vogon/blob/master/sample_project/sample.json) and another for [Windows](https://github.com/googleads/vogon/blob/master/sample_project/sample_win.json). You can use one of these as a starting point for your project.

####Variables

In most values, you can use variables to insert values from the input CSV. For example, you can use the location name from the CSV to specify the geo-targeting for the campaigns.

The syntax for variables is `{{column name}}`, where "column name" is the name in the CSV header. For example, if your CSV looks like this:


City | Price
---- | -----
São Paulo | 48.900,00
Curitiba | 49.900,00

You can configure geo-targeting like this:

`"Location": "{{city}}"`

Column names are case-insensitive (e.g. "City" and "city" both work).

Vogon pre-defines some special variables that don't come from the CSV:

`{{$id}}`: a sequential line number of the record in the CSV file (starting at 1, after the header). It can be useful to generate video files with unique names, for example.

`{{$video_id}}`: After a video is uploaded to YouTube, this is the video ID. It can be used for linking to the video. The "Video Id" ad attribute in the output CSV is automatically set to this value.

#### Importing the Campaigns

Vogon will generate a CSV file that can be imported into AdWords for Video, containing all the new campaigns, ads and targeting for the generated videos. This file can be modified with a text editor or spreadsheet application (like LibreOffice or Excel), if necessary, or imported as is.

If you want to insert ads into existing campaigns, you'll need to obtain the campaign ID. To do that, click the "Bulk Upload" button, choose the "Only Data" option and click "Download". The generated file will contain the campaign ID numbers.

#### Reference

AdWords for Video bulk upload documentation: https://support.google.com/youtube/answer/3344649

#### Location Codes

Location names need to be followed by their codes, which can be looked up in this page: https://developers.google.com/adwords/api/docs/appendix/geotargeting. The prefix "47-" needs to be added to the code that you look up from the page.

For example:

    São Paulo, Brazil  (47-20106)
    Florianopolis, SC, Brazil (47-1001706)

If the codes are present, the names are not really important, as the system will use the code to look up the location. If the code is absent, the system will try to find the location by name, but this is unreliable and can lead to missing or incorrect locations.
