var $ = require('jquery');
var blueslip = require('./blueslip');

$.fn.expectOne = function () {
    if (this.length !== 1) {
        blueslip.error("Expected one element in jQuery set, " + this.length + " found");
    }
    return this;
};

module.exports = $;
