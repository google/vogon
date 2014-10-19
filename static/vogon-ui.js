
angular.module('vogonUiApp', [])
  .controller('VogonUiController', ['$scope', '$http', function($scope, $http) {
    $http.get('/config').success(function(data) {
        $scope.config = data;
    });

    $scope.getConfig = function() {
        return angular.toJson($scope.config, true);
    };

    $scope.saveConfig = function() {
        $http.post('/config', $scope.config);
    };
 
    $scope.addText = function() {
      $scope.config.text_lines.push({
          x: "0",
          y: "0",
          start_time: "0",
          end_time: "0",
          text: "",
          font: "",
          font_size: "80",
          font_color: "#000000"
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

    $scope.delete = function(arr, i) {
        arr.splice(i, 1);
    };
 
}]);
