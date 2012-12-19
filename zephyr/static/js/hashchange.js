var hashchange = (function () {

var exports = {};

var expected_hash = false;

exports.changehash = function (newhash) {
    expected_hash = newhash;
    // Some browsers reset scrollTop when changing the hash to "",
    // so we save and restore it.
    // http://stackoverflow.com/questions/4715073/window-location-hash-prevent-scrolling-to-the-top
    var scrolltop;
    if (newhash === "") {
        scrolltop = viewport.scrollTop();
    }
    window.location.hash = newhash;
    util.reset_favicon();
    if (newhash === "") {
        viewport.scrollTop(scrolltop);
    }
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
    switch (hash[0]) {
        case "#narrow":
            ui.change_tab_to("#home");
            narrow.hashchanged(hash);
            ui.update_floating_recipient_bar();
            break;
        case "":
        case "#":
            ui.change_tab_to("#home");
            narrow.show_all_messages();
            ui.update_floating_recipient_bar();
            break;
        case "#subscriptions":
            ui.change_tab_to("#subscriptions");
            break;
        case "#settings":
            ui.change_tab_to("#settings");
            break;
    }
}

exports.initialize = function () {
    window.onhashchange = hashchanged;
    hashchanged();
};

return exports;

}());
