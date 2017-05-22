var common = require("js/common.js");

set_global('$', function (f) {
    if (f === '#home') {
        return [{ focus: function () {} }];
    }
    f();
});

(function test_basics() {
    common.autofocus('#home');
}());
