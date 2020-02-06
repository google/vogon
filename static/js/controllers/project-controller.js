/*
Copyright 2019 Google Inc. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

app.controller('ProjectController',
               ['$scope', '$http', '$cookies', '$routeParams', 'AssetsResource',
                'Upload', 'YouTubeApi', 'SheetsFeed', '$sce',
                function($scope, $http, $cookies, $routeParams,
                         AssetsResource, Upload, YouTubeApi, SheetsFeed, $sce) {
    console.log("project " + $routeParams.project);

    // Genral
    $scope.project_id = $routeParams.project;
    $scope.project_url = "/api/projects/" + $routeParams.project + "/";
    $scope.config_debug = null;
    $scope.generatingPreview = false;
    $scope.previewIndex = 1;
    $scope.config = {};
    $scope.tabs = {};
    $scope.currentNavItem = 'video_conf_tab';
    $scope.hide_preview=true;
    $scope.generated_videos_count = 0;
    $scope.linked_channel = 'None';
    $scope.log = function(msg){console.log(msg); alert(msg);};
    $scope.feed_ok = false;
    $scope.feed_sce = "";

    // video generation
    $scope.preview = generatePreview;
    $scope.generate_all_variations = generateAllVariations;
    $scope.cancel_video_generation = cancelVideoGeneration;
    $scope.is_updating_video_generation = false;

    // Assets
    $scope.assets = [];
    $scope.fonts = [];
    $scope.video_assets = [];
    $scope.image_assets = [];
    $scope.load_assets = loadAssetsList;
    $scope.showAssets = false;
    $scope.downloadAsset = downloadAsset;
    $scope.upload_single_asset = upload_single_asset;
    $scope.asset_upload_message = '';
    $scope.removeAsset = removeAsset;
    $scope.reload_assets = reload_assets;

    // Feed
    $scope.readTrixFeed = readTrixFeed;
    $scope.loadFeedFromSpreadsheet = loadFeedFromSpreadsheet;
    $scope.setDataFileUri = setDataFileUri;

    // Google Ads CSV
    $scope.csv_download_message = "";
    $scope.getGoogleAdsEditorCSV = getGoogleAdsEditorCSV;

    //Youtube
    $scope.youtube_auth = {
      device_code: undefined,
      verification_url: undefined,
      user_code: undefined,
      access_token: undefined,
      refresh_token: undefined,
      token_type: undefined
    };

    $scope.is_updating_video_upload = false;
    $scope.youtube_channel = undefined;
    $scope.video_upload = {
      current_state: "--"
    };

    $scope.authorize_youtube = function() {
      $scope.youtube_channel_auth_box = true;
      YouTubeApi.getAuthorizationCode().then(function(result){
        $scope.youtube_auth.device_code = result.data.device_code;
        $scope.youtube_auth.verification_url = result.data.verification_url;
        $scope.youtube_auth.user_code = result.data.user_code;
      });
    };

    $scope.check_authorized_device = function() {
      YouTubeApi.checkAuthorizedDevice($scope.youtube_auth.device_code).then(function(result) {
        update_youtube_tokens(result.data);
        $scope.get_channel_name();
      }, function(result) {
        alert(result.data.error_description);
      });
    }

    $scope.get_channel_name = function() {
      var access_token = $cookies.get('yt_access_token');
      var refresh_token = $cookies.get('yt_refresh_token');

      if(access_token != undefined && refresh_token != undefined) {
        YouTubeApi.listChannels(access_token, refresh_token).then(function(result) {
          update_youtube_tokens(result.data);

          if(result.data.items.length > 0){
            $scope.youtube_channel = result.data.items[0];
            $scope.youtube_channel_auth_box = false;
          }
        });
      }
    }

    $scope.start_video_upload = function() {

      /*if($scope.generated_videos_count == 0) {
        alert("No videos found!");
        return;
      }*/

      updateVideoUpload();
      YouTubeApi.startVideoUpload(
        $cookies.get('yt_access_token'),
        $cookies.get('yt_refresh_token'),
        $scope.project_id,
        $scope.youtube_channel.id,
        $scope.config.video_title,
        $scope.config.video_description);
    }

    $scope.remove_uploaded_videos = function() {
      updateVideoUpload();
      YouTubeApi.removeUploadedVideos(
        $cookies.get('yt_access_token'),
        $cookies.get('yt_refresh_token'),
        $scope.project_id,
        $scope.youtube_channel.id);
    }

    function update_youtube_tokens(tokens) {
      if(tokens.access_token != undefined)
        $cookies.put('yt_access_token', tokens.access_token);

      if(tokens.refresh_token != undefined)
        $cookies.put('yt_refresh_token', tokens.refresh_token);

      if(tokens.token_type != undefined)
        $cookies.put('yt_token_type', tokens.token_type);
    }
    $scope.set_feed_tab = function(){
      if($scope.config.sheets_url.indexOf("https://") === 0){
        $scope.feed_ok = true;
        $scope.feed_sce = $sce.trustAsResourceUrl($scope.config.sheets_url);
      }else{
        $scope.feed_ok = false;
        $scope.feed_sce = "";
      }
    }

    function main(){
      var scope = $scope;
      $scope.load_assets();
      $http.get($scope.project_url + 'config').then(function(data) {
          scope.config = data.data;
          scope.config_debug = scope.getConfig(scope);
          scope.set_feed_tab();
      });
      updateVideoGeneration();
      updateVideoUpload();
      $scope.get_channel_name();
    }

    $scope.getConfig = function() {
        return angular.toJson($scope.config, true);
    };

    $scope.saveConfig = function(success) {
        $http.post($scope.project_url + 'config', $scope.config)
            .then(success);
    };

    $scope.goto = function(tab_id){
      var tabs = ["files_conf_tab",   "video_conf_tab", "youtube_conf_tab",
                  "adw_conf_tab", "feed_conf_tab"];
        for(var i in tabs)
          $scope.tabs[tabs[i]] = !(tab_id == tabs[i]);
    };

    $scope.goto('video_conf_tab');

    $scope.addText = function() {
      $scope.config.text_lines.push({
          x: "0",
          y: "0",
          h_align: "left",
          start_time: "0",
          end_time: "0",
          text: "",
          font: "",
          is_cropped_text: false,
          font_size: "80",
          font_color: "#000000",
          angle: ""
          });
    };

    $scope.addImage = function() {
      $scope.config.images.push({
          x: "0",
          y: "0",
          start_time: "0",
          end_time: "0",
          image: ""
          });
    };

    $scope.addTarget = function() {
        $scope.config.adwords.targets.push({
           max_cpv: "",
           type: "Keyword",
           value: "",
           level: "Target Group"
           });
      };

    $scope.delete = function(arr, i) {
        arr.splice(i, 1);
    };

    function generatePreview() {
        $scope.generatingPreview = true;
        $scope.hide_preview = false;
        $scope.saveConfig(function(data, status, headers, config) {
            var cacheBust = String(Math.random());
            //$scope.previewVideo = '/preview/' + $scope.previewIndex + '?' + cacheBust;
            // I'm not supposed to manipulate the DOM here, but I haven't figured out the idiomatic way to do it yet.
            var elem = document.getElementById('previewPlayer');
            elem.onerror = function() {
              var e = elem.error;
              console.log("Error " + e.code + "; details: " + e.message);
              alert("Error " + e.code + "; details: " + e.message);
            };
            elem.src = $scope.project_url +'preview/row/' + $scope.previewIndex + '?' + cacheBust;
            elem.load();
        });
    }

    $scope.previewLoaded = function() {
        $scope.generatingPreview = false;
    };

    function generateAllVariations(){
      var uri = "/api/projects/" + $scope.project_id + "/generate_all_videos";
      $http.post(uri).then(function(data) {
        updateVideoGeneration();
      });
    }

    function cancelVideoGeneration(){
      var uri = "/api/projects/" + $scope.project_id + "/cancel_video_generation";
      $http.get(uri).then(function(data) {
          $scope.video_generation = "Video generation cancelled.";
      });
    }

    function updateVideoGeneration(){
      if($scope.is_updating_video_generation === false){
        $scope.is_updating_video_generation = true;
        __loopUpdateVideoGeneration();
      }
    }

    function updateVideoUpload(){
      if($scope.is_updating_video_upload === false){
        $scope.is_updating_video_upload = true;
        setTimeout(__loopUpdateVideoUpload, 1000);
      }
    }

    function __loopUpdateVideoUpload(){
      var scope = $scope;
      if(scope.is_updating_video_upload){
        if(!scope.tabs["youtube_conf_tab"]){
          var uri = "/api/youtube/read_log/" + scope.project_id;
          $http.get(uri).then(function(data) {
            scope.video_upload.current_state = data.data;
          });
        }
        setTimeout(__loopUpdateVideoUpload, 5000);
      }
    }

    function __loopUpdateVideoGeneration(){
      var scope = $scope;
      if(scope.is_updating_video_generation){
        if(!scope.tabs['video_conf_tab']){
          var uri = "/api/projects/" + scope.project_id + "/update_on_video_generation";
          $http.get(uri).then(function(data) {
            scope.video_generation = data.data;
          });
        }
        setTimeout(__loopUpdateVideoGeneration, 5000);
      }
    }

    $scope.reverse = function(color){
      function invertColor(hex) {
          // Clean up and ensure hex format
          if (hex.indexOf('#') == 0)
              hex = hex.slice(1);

          if (hex.length == 3)
              hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];

          if (hex.length != 6)
              console.log('Invalid HEX color.');
              return

          // extract RGB colors
          var red = hex.slice(0, 2);
          var green = hex.slice(2, 4);
          var blue = hex.slice(4, 6);

          // invert colors
          var red_inverted = invert_color(red)
          var green_inverted = invert_color(green);
          var blue_inverted = invert_color(blue);

          // return in HEXA format
          return '#' + red_inverted + green_inverted + blue_inverted;
      }

      function invert_color(color){
        color = parseInt(color, 16);
        var inverted = 255 - color;
        inverted = add_zero(inverted.toString(16));
        return inverted;
      }

      function pad(str, len) {
          len = len || 2;
          var zeros = new Array(len).join('0');
          return (zeros + str).slice(-len);
      }
      if(color.length === 7)
        return invertColor(color);
      else
        return "#000000";
    };

    // <Assets management functions>
    function upload_single_asset(files) {
      var uploaded = 0;
      var total_uploads = files.length;
      if (files && files.length) {
        for (var i = 0; i < files.length; i++) {
          var file = files[i];
          Upload.upload({url: $scope.project_url + 'assets', file: file})
              .success(function(data, status, headers, config) {
                $scope.asset_upload_message = 'Upload finished!';
                uploaded += 1;
                if (uploaded == files.length) {
                  $scope.load_assets();
                }
              })
              .progress(function(evt) {
                var progressPercentage =
                    parseInt(100.0 * evt.loaded / evt.total);
                var msg =
                    'Uploaded ' + uploaded + ' of ' + total_uploads + ' files.';
                msg +=
                    'Currently uploading file "' + evt.config.file.name + '"';
                msg += ' - ' + progressPercentage + '% Uploaded ';
                $scope.asset_upload_message = msg;
              });
        }
      }
    }

    function getFonts(){
      var fonts_url = "/api/projects/" + $scope.project_id + "/fonts";
      $http.get(fonts_url).then(function(data) {
          $scope.fonts = data.data;
      });
    }

    function loadAssetsList() {
      AssetsResource.getList(
          {project_id: $scope.project_id}, $scope.reload_assets);
    }

    function reload_assets(assets) {
      getFonts();
      $scope.assets = [];
      function get_icon(path) {
        var file_type = path.split('.');
        file_type = file_type[file_type.length - 1];
        switch (file_type.toLowerCase()) {
          case 'mp4':
            return 'videocam';
          case 'mov':
            return 'videocam';
          case 'flv':
            return 'videocam';
            case 'mp3':
            return 'audiotrack';
          case 'wav':
            return 'audiotrack';
          case 'wave':
            return 'audiotrack';
          case 'jpg':
            return 'photo';
          case 'jpeg':
            return 'photo';
          case 'png':
            return 'photo';
          case 'gif':
            return 'photo';
          default:
            return 'insert_drive_file';
        }
      }
      $scope.image_assets = []
      $scope.video_assets = [];
      $scope.image_and_video_assets = [];
      for (var i in assets) {
        if (typeof assets[i] == 'string') {
          var asset_name = (assets[i].indexOf('assets/') == 0) ?
              assets[i].replace('assets/', '') :
              assets[i];
          var asset = {
            'name': asset_name,
            'path': assets[i],
            'icon': get_icon(assets[i])
          }
          $scope.assets.push(asset);
          if(asset.icon == "photo")
            $scope.image_assets.push(asset.name)
          if(asset.icon == "videocam")
            $scope.video_assets.push(asset.name)
        }
      }
      var iv_arr = [];
      iv_arr = iv_arr.concat($scope.image_assets);
      iv_arr = iv_arr.concat($scope.video_assets);
      $scope.image_and_video_assets = iv_arr;
    }

    function removeAsset(asset_path) {
      msg = 'Are you sure you want to remove this asset? This is irreversible.';
      if (confirm(msg)) {
        AssetsResource.removeAsset(
            {project_id: $scope.project_id, asset_path: asset_path},
            $scope.reload_assets);
      }
    }

    function downloadAsset(asset_path) {
      AssetsResource.getDownloadableLink(
          {project_id: $scope.project_id, asset_path: asset_path},
          function(data) {
            console.log(data);
            window.location.href = data.file_url;
          });
    }

    function makePathRelativeToAssets(uri) {
      if (uri.indexOf('assets/') != 0) {
        return 'assets/' + uri;
      }
    }

    // </Assets management functions>



    // <Upload feed from Google Sheets function>
    function showFeedProgress(msg) {
      $scope.feed_progress = msg;
    }

    function loadFeedFromSpreadsheet(ev) {
      msg = 'Enter the URL of the Google Sheets spreadsheet containing the ';
      msg += 'feed. The data must be in a tab named "feed".';
      var urlInput =
          $mdDialog.prompt()
              .title('Spreadsheet URL')
              .textContent(msg)
              .ariaLabel('Feed Spreadsheet URL')
              .initialValue($scope.config.trix_url)
              .targetEvent(ev)
              .ok('OK')
              .cancel('Cancel');

      $mdDialog.show(urlInput).then(
          function(result) {
            $scope.readTrixFeed(result);
          },
          function() {});
    }

    function readTrixFeed(trix_url) {
      var msg = 'Downloading feed from Google Sheets... (1/3)';
      showFeedProgress(msg);
      SheetsFeed.loadFeed(trix_url, function(response) {
        if (response.success) {
          msg = 'Feed downloaded successfully.';
          showFeedProgress(msg);
          uploadFeedToBackend(response.data, trix_url);
        } else {
          var msg = 'There was an error reading your spreadsheet:';
          msg += ' \'' + JSON.stringify(response.msg) + '\'.';
          showFeedProgress(msg);
        }
      });
    }

    function uploadFeedToBackend(data, trix_url) {
      var msg = 'Updating your Vogon feed... (2/3)';
      showFeedProgress(msg);
      var url = $scope.project_url + 'feed_content_upload';
      var data = {feed_data: data, project_id: $scope.project_id};
      // saves feed
      $http.post(url, data).then(
          function(response) {
            var rs = response.data;
            if (rs.success) {
              msg = 'Feed saved successfully. Updating config... (3/3)';
              showFeedProgress(msg);
              // updates config
              $scope.config.trix_url = trix_url;
              $scope.config.data_file = 'feed.csv';
              $scope.saveConfig(
                  function(data, status, headers, config) {
                msg = "Feed and Config updated successfully :)";
                showFeedProgress(msg);
                $scope.set_feed_tab();
              });
            } else {
              msg = 'There was an error saving your feed locally:';
              msg += ' \'' + JSON.stringify(rs.msg) + '\'.';
              showFeedProgress(msg);
            }
          },
          function(response) {
            var msg = 'There was an error saving your feed locally';
            msg += ' \'' + JSON.stringify(response) + '\'.';
            showFeedProgress(msg);
          });
    }

    function setDataFileUri() {
      var val = $scope.config.data_file;
      if ($scope.config.data_file == 'feed.csv' &&
          $scope.config.trix_url) {
        val = $scope.config.trix_url;
      }
      $scope.config.data_file_uri = val;
    }
    // </Upload feed from Google Sheets function>


    function getGoogleAdsEditorCSV(){
      var url = '/api/projects/' + $scope.project_id + '/google_ads_editor_file';
      $http.get(url).then(function(data) {
          console.log(data.data)
          if(!data.data["msg"]){
            $scope.csv_download_message = "Success download :)";
            window.location.href = url;
          }else{
            $scope.csv_download_message = data.data.msg;
          }
      });
    }


    main();

}]);
