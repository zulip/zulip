var hashchange = (function () {

var exports = {};

var expected_hash = false;

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).

function encodeHashComponent(str) {
    return encodeURIComponent(str)
        .replace(/\./g, '%2E')
        .replace(/%/g,  '.');
}

function decodeHashComponent(str) {
    return decodeURIComponent(str.replace(/\./g, '%'));
}

exports.changehash = function (newhash) {
    expected_hash = newhash;
    // Some browsers reset scrollTop when changing the hash to "",
    // so we save and restore it.
    // http://stackoverflow.com/questions/4715073/window-location-hash-prevent-scrolling-to-the-top
    var scrolltop = viewport.scrollTop();
    window.location.hash = newhash;
    util.reset_favicon();
    if (newhash === "" || newhash === "#") {
        viewport.scrollTop(scrolltop);
    }
};

exports.save_narrow = function (operators) {
    if (operators === undefined) {
        exports.changehash('#');
    } else {
        var new_hash = '#narrow';
        $.each(operators, function (idx, elem) {
            new_hash += '/' + encodeHashComponent(elem[0])
                      + '/' + encodeHashComponent(elem[1]);
        });
        exports.changehash(new_hash);
    }
};

function parse_narrow(hash) {
    var i, operators = [];
    for (i=1; i<hash.length; i+=2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        var operator = decodeHashComponent(hash[i]);
        var operand  = decodeHashComponent(hash[i+1] || '');
        operators.push([operator, operand]);
    }
    var new_selection;
    if (current_msg_list.selected_id() !== -1) {
        new_selection = current_msg_list.selected_id();
    } else {
        new_selection = initial_pointer;
    }
    narrow.activate(operators, {
        then_select_id: new_selection,
        change_hash:    false  // already set
    });
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

    // NB: In Firefox, window.location.hash is URI-decoded.
    // Even if the URL bar says #%41%42%43%44, the value here will
    // be #ABCD.
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
            narrow.deactivate();
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
        load_more_messages(current_msg_list);
    }
};

return exports;

}());
