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

// start angular
var app = angular.module('vogonUiApp',
                         ['ngRoute', 'ngCookies', 'ngMaterial', 'ngMessages', 'ngSanitize',
                          'ngResource', 'ngFileUpload', 'sheetsApiService',
                          'youtubeApiService']);



// setup routes
app.config(function($mdThemingProvider, $routeProvider) {
  $routeProvider
    .when('/', {
      templateUrl: '/static/html/list-projects.html',
      controller: 'ProjectListController'
    })
    .when('/project/:project', {
      templateUrl: '/static/html/project.html',
      controller: 'ProjectController'
    }).otherwise({
        redirectTo: '/'
    });
});


// setup layout
app.config(function($mdThemingProvider, $routeProvider) {
  $mdThemingProvider.definePalette('vogonPallete', {
    '50': '54b2f6',
    '100': '54b2f6',
    '200': 'ef9a9a',
    '300': 'e57373',
    '400': 'ef5350',
    '500': '54b2f6',
    '600': 'e53935',
    '700': 'd32f2f',
    '800': 'c62828',
    '900': 'b71c1c',
    'A100': 'ff8a80',
    'A200': 'ff5252',
    'A400': 'ff1744',
    'A700': 'd50000',
    'contrastDefaultColor': 'light',

    'contrastDarkColors': ['50', '100',
     '200', '300', '400', 'A100'],
    'contrastLightColors': undefined
  });
  $mdThemingProvider.theme('default')
    .primaryPalette('vogonPallete')
    .accentPalette('red');

});

function previewLoaded(element) {
    var scope = angular.element(element).scope();
    scope.previewLoaded();
    scope.$apply();
    element.play();
};
