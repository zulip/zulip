var hashchange = (function () {

var exports = {};

var expected_hash = false;

exports.changehash = function (newhash) {
    expected_hash = newhash;
    window.location.hash = newhash;
};

function hashchanged() {
    // If window.location.hash changed because our app explicitly
    // changed it, then we don't need to do anything.
    // (This function only neds to jump into action if it changed
    // because e.g. the back button was pressed by the user)
    if (window.location.hash === expected_hash) {
        return;
    }

    var hash = window.location.hash.split("/");
    if (hash[0] === "#narrow") {
        narrow.hashchanged(hash);
        ui.update_floating_recipient_bar();
    }
    else if (narrow.active()) {
        narrow.show_all_messages();
        ui.update_floating_recipient_bar();
    }
}

exports.initialize = function () {
    window.onhashchange = hashchanged;
};

return exports;

}());
