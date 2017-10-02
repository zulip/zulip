var loader = (function () {

var exports = {};

exports.show_loader = function (btn_id) {
   console.log("I am in");
}

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = loader;
}