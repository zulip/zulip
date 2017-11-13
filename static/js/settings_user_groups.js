var settings_user_groups = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.set_up = function () {
    meta.loaded = true;
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_user_groups;
}
