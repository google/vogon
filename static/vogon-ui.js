
angular.module('vogonUiApp', [])
  .controller('VogonUiController', ['$scope', '$http', function($scope, $http) {

    $scope.generatingPreview = false;
    $scope.previewIndex = 1;

    $http.get('/config').success(function(data) {
        $scope.config = data;
    });

    $scope.getConfig = function() {
        return angular.toJson($scope.config, true);
    };

    $scope.saveConfig = function(success) {
        $http.post('/config', $scope.config).success(success);
    };
 
    $scope.addText = function() {
      $scope.config.text_lines.push({
          x: "0",
          y: "0",
          h_align: "left",
          start_time: "0",
          end_time: "0",
          text: "",
          font: "",
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

    $scope.preview = function() {
        $scope.generatingPreview = true;
        $scope.saveConfig(function(data, status, headers, config) {
            var cacheBust = String(Math.random());
            //$scope.previewVideo = '/preview/' + $scope.previewIndex + '?' + cacheBust;
            // I'm not supposed to manipulate the DOM here, but I haven't figured out the idiomatic way to do it yet.
            var elem = document.getElementById('previewPlayer')
            elem.src = '/preview/' + $scope.previewIndex + '?' + cacheBust;
            elem.load();
        });
    };

    $scope.previewLoaded = function() {
        $scope.generatingPreview = false;
    };
 
}]);

function previewLoaded(element) {
    var scope = angular.element(element).scope();
    scope.previewLoaded();
    scope.$apply();
    element.play();
}

