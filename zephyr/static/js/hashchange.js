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

exports.save_narrow = function (operators) {
    if (operators === undefined) {
        exports.changehash('#');
    } else {
        var new_hash = '#narrow';
        $.each(operators, function (idx, elem) {
            new_hash += '/' + encodeURIComponent(elem[0])
                      + '/' + encodeURIComponent(elem[1]);
        });
        exports.changehash(new_hash);
    }
};

function parse_narrow(hash) {
    var i, operators = [];
    for (i=1; i<hash.length; i+=2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        var operator = decodeURIComponent(hash[i]);
        var operand  = decodeURIComponent(hash[i+1] || '');
        operators.push([operator, operand]);
    }
    narrow.activate(operators);
}

// Returns true if this function performed a narrow
function hashchanged() {
    // If window.location.hash changed because our app explicitly
    // changed it, then we don't need to do anything.
    // (This function only neds to jump into action if it changed
    // because e.g. the back button was pressed by the user)
    if (window.location.hash === expected_hash) {
        return false;
    }

    var hash = window.location.hash.split("/");
    switch (hash[0]) {
        case "#narrow":
            ui.change_tab_to("#home");
            parse_narrow(hash);
            ui.update_floating_recipient_bar();
            return true;
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
    return false;
}

exports.initialize = function () {
    window.onhashchange = hashchanged;
    if (hashchanged()) {
        load_more_messages();
    }
};

return exports;

}());
