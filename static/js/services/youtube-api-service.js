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
var youtubeApiService = angular.module('youtubeApiService', []);

// Returns data from Google SpreadSheets API
youtubeApiService.factory('YouTubeApi', [
    '$resource', '$http',
    function($resource, $http) {
      function getAuthorizationCode() {
        var auth_url = '/api/youtube_auth/get_device_code';
        
        return $http({
          method: 'POST',
          url: auth_url
        });
      }

      function checkAuthorizedDevice(device_code) {
        var poll_url = "/api/youtube_auth/check_device_authorization";
        var poll_data = {
          code: device_code
        };

        return $http({
          method: 'POST',
          url: poll_url,
          data: poll_data
        });
      }

      function listChannels(access_token, refresh_token) {
        return $http({
          method: "POST",
          url: "/api/youtube/list_channels",
          data: {
            access_token: access_token,
            refresh_token: refresh_token
          },
        })
      }

      function startVideoUpload(
        access_token, refresh_token, project_id, channel_id, title, description) {
          return $http({
            method: "POST",
            url: "/api/youtube/start_video_upload",
            data: {
              access_token: access_token,
              refresh_token: refresh_token,
              project_id: project_id,
              channel_id: channel_id,
              title: title,
              description: description
            }
          });
      }

      function removeUploadedVideos(
        access_token, refresh_token, project_id, channel_id) {
          return $http({
            method: "POST",
            url: "/api/youtube/remove_uploaded_videos",
            data: {
              access_token: access_token,
              refresh_token: refresh_token,
              project_id: project_id,
              channel_id: channel_id
            }
          });
      }

      // returns factory object
      return {
        getAuthorizationCode: getAuthorizationCode,
        checkAuthorizedDevice: checkAuthorizedDevice,
        listChannels: listChannels,
        startVideoUpload: startVideoUpload,
        removeUploadedVideos: removeUploadedVideos
      };
    }
]);