var common = require("js/common.js");

set_global('$', global.zjquery);

(function test_basics() {
    common.autofocus('#home');
    assert($('#home').is_focused());
}());
