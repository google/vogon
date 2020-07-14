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

app.controller('ProjectListController',
               ['$scope', '$http', '$location', function($scope, $http, $location) {
   console.log("project list");
   $scope.projects = [];
   $scope.loading = true;
   var scope = $scope;
    $http.get('/api/projects/list').then(function(data) {
      scope.projects = data.data;
      scope.loading = false;
    });

   // Copies base project
   $scope.create = function(){
     var response = prompt("What is your project name? \n(use only a-z or _ )");
     if(response){
       console.log(response);
       $scope.loading = true;
       $scope.projects = [];

       $http.post('/api/projects/new/name/'+response).then(function(data) {
         if(data.data.success)
           $location.path("/project/"+data.data.project);
         else{
           alert("A project with name '"+data.data.project+"' already exists");
           $http.get('/api/projects/list').then(function(data) {
            scope.projects = data.data;
            scope.loading = false;
            });
         }
       });
     }
   };

  $scope.delete = function(project){
    $scope.loading = true;
    if(confirm("[Project '"+project+"'] You will lose all project files, including configs and assets.")){
      if(confirm("[Project '"+project+"'] Are you sure you want to remove the project? this action is irreversible!")){
        $http.post('/api/projects/'+ project +'/delete').then(function(data) {
         $http.get('/api/projects/list').then(function(data) {
              scope.projects = data.data;
              scope.loading = false;
              });
        });
      }else{
        $scope.loading = false;
      }
    }else{
      $scope.loading = false;
    }
  };

  $scope.clear = function(project){
    $scope.loading = true;
    if(confirm("[Project '"+project+"'] Clear the project means all generated videos will be removed. None of configs or assets or base videos will be removed. This is useful to reduce used space. Are you sure you want to continue?")){
      $http.post('/api/projects/'+ project +'/clear').then(function(data) {
         $http.get('/api/projects/list').then(function(data) {
              $scope.projects = data.data;
              $scope.loading = false;
          });
        });
    }else{
      $scope.loading = false;
    }
  };
}]);


