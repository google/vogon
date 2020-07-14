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

app.factory('AssetsResource', ['$resource', '$http',
                               function($resource, $http) {
      var resource_url = '/api/projects/:project_id/assets';
      var resource_actions = {
          'getList': {
            method: 'GET',
            isArray: true
          },
          'removeAsset': {
            method: 'DELETE',
            isArray: true,
            url: resource_url + '/?asset_path=:asset_path'
          }
      };
      var resource_params = null;

      var resource =  $resource(resource_url, resource_params, resource_actions);

      resource.getDownloadableLink = function(payload_data, callback){
        var project_id = payload_data.project_id;
        var asset = payload_data.asset_path;
        asset = encodeURIComponent(asset);
        var url = "/api/projects/" + project_id + "/download/assets/?asset_path=" + asset ;
        callback({file_url:url});
      };

      return resource;
    }
]);

