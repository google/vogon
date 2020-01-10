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
var sheetsApiService = angular.module('sheetsApiService', []);

// Returns data from Google SpreadSheets API
sheetsApiService.factory('SheetsFeed', [
    '$resource', '$http',
    function($resource, $http) {
      var CLIENT_ID = null;
      var SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"];

      // starter of feed download from Spreadsheet URL
      function loadFeed(sheet_url, callback) {
        // gets id from Spreadsheet URL
        var id = sheet_url;
        var urls = [
            "https://docs.google.com/spreadsheets/d/",
            "http://docs.google.com/spreadsheets/d/",
            "https://docs.google.com/a/google.com/spreadsheets/d/",
            "http://docs.google.com/a/google.com/spreadsheets/d/"
        ];
        for ( var j in urls) {
          id = id.replace(urls[j], "");
        }
        id = id.split("/")[0];

        // authorizes and load data from Spreadsheet
        AuthorizeAndLoadFeed(callback, id);
      }

      // Check if current user has authorized this application.
      function AuthorizeAndLoadFeed(callback, spreadsheet_id) {
        var auth_client = function(CLIENT_ID) {
          gapi.auth.authorize({
              'client_id': CLIENT_ID,
              'scope': SCOPES.join(' '),
              'immediate': false
          }, function(authResult) {
            handleFeedAuthResult(authResult, callback, spreadsheet_id);
          });
        };
        if(CLIENT_ID != null){
          auth_client(CLIENT_ID);
        }else{
          $http.get("/api/sheets_client_id").then(function(data) {
            CLIENT_ID = JSON.parse(data.data);
            auth_client(CLIENT_ID);
          });
        }
      }

      // Handle response from authorization server.
      function handleFeedAuthResult(authResult, callback, spreadsheet_id) {
        if (authResult && !authResult.error) {
          loadSheetsApiForFeed(callback, spreadsheet_id);
        } else {
          var error_json = JSON.stringify(authResult);
          var msg = "There was an error authenticating with Google Drive.";
          msg += "Please try again. Full error msg:" + error_json;
          var rs = {
              success: false,
              msg: msg
          };
          callback(rs);
        }
      }

      // Load Sheets API client library.
      function loadSheetsApiForFeed(callback, spreadsheet_id) {
        var discoveryUrl = 'https://sheets.googleapis.com';
        discoveryUrl += '/$discovery/rest?version=v4';
        gapi.client.load(discoveryUrl).then(function() {
          callbackFeed(callback, spreadsheet_id);
        });
      }

      // Returns the content or error to caller
      function callbackFeed(callback, spreadsheet_id) {
        gapi.client.sheets.spreadsheets.values.get({
            spreadsheetId: spreadsheet_id,
            range: 'feed',
        }).then(function(response) {
          var range = response.result;
          if (range.values.length > 0) {
            var rs = {
                success: true,
                msg: "Data loaded with success!",
                data: range.values
            };
            callback(rs);
          } else {
            var msg = "No data found in specified spreadsheet. Make sure you ";
            msg += "have access and it contains a sheet named 'feed'.";
            var rs = {
                success: false,
                msg: msg
            };
            callback(rs);
          }
        }, function(response) {
          var msg = "Error loading your spreadsheet. Error: ";
          msg += response.result.error.message;
          var rs = {
              success: false,
              msg: msg
          };
          callback(rs);
        });
      }

      // returns factory object
      return {
        loadFeed: loadFeed
      };
    }
]);
