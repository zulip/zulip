var hashchange = (function () {

var exports = {};

var expected_hash;
var changing_hash = false;

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).

exports.encodeHashComponent = function (str) {
    return encodeURIComponent(str)
        .replace(/\./g, '%2E')
        .replace(/%/g,  '.');
};

function decodeHashComponent(str) {
    return decodeURIComponent(str.replace(/\./g, '%'));
}

function set_hash(hash) {
    var location = window.location;

    if (history.pushState) {
        if (hash === '' || hash.charAt(0) !== '#') {
            hash = '#' + hash;
        }

        // IE returns pathname as undefined and missing the leading /
        var pathname = location.pathname;
        if (pathname === undefined) {
            pathname = '/';
        } else if (pathname === '' || pathname.charAt(0) !== '/') {
            pathname = '/' + pathname;
        }

        // Build a full URL to not have same origin problems
        var url =  location.protocol + '//' + location.host + pathname + hash;
        history.pushState(null, null, url);
    } else {
        location.hash = hash;
    }
}

exports.changehash = function (newhash) {
    if (changing_hash) {
        return;
    }
    $(document).trigger($.Event('hashchange.zulip'));
    set_hash(newhash);
    favicon.reset();
};

// Encodes an operator list into the
// corresponding hash: the # component
// of the narrow URL
exports.operators_to_hash = function (operators) {
    var hash = '#';

    if (operators !== undefined) {
        hash = '#narrow';
        _.each(operators, function (elem) {
            // Support legacy tuples.
            var operator = elem.operator;
            var operand = elem.operand;

            var sign = elem.negated ? '-' : '';
            hash += '/' + sign + hashchange.encodeHashComponent(operator)
                  + '/' + hashchange.encodeHashComponent(operand);
        });
    }

    return hash;
};

exports.save_narrow = function (operators) {
    if (changing_hash) {
        return;
    }
    var new_hash = exports.operators_to_hash(operators);
    exports.changehash(new_hash);
};

function parse_narrow(hash) {
    var i, operators = [];
    for (i=1; i<hash.length; i+=2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        try {
            var operator = decodeHashComponent(hash[i]);
            var operand  = decodeHashComponent(hash[i+1] || '');
            var negated = false;
            if (operator[0] === '-') {
                negated = true;
                operator = operator.slice(1);
            }
            operators.push({negated: negated, operator: operator, operand: operand});
        } catch (err) {
            return undefined;
        }
    }
    return operators;
}

function activate_home_tab() {
    ui.change_tab_to("#home");
    narrow.deactivate();
    floating_recipient_bar.update();
}

// Returns true if this function performed a narrow
function do_hashchange(from_reload) {
    // If window.location.hash changed because our app explicitly
    // changed it, then we don't need to do anything.
    // (This function only neds to jump into action if it changed
    // because e.g. the back button was pressed by the user)
    //
    // The second case is for handling the fact that some browsers
    // automatically convert '#' to '' when you change the hash to '#'.
    if (window.location.hash === expected_hash ||
        (expected_hash !== undefined &&
         window.location.hash.replace(/^#/, '') === '' &&
         expected_hash.replace(/^#/, '') === '')) {
        return false;
    }

    $(document).trigger($.Event('hashchange.zulip'));

    // NB: In Firefox, window.location.hash is URI-decoded.
    // Even if the URL bar says #%41%42%43%44, the value here will
    // be #ABCD.
    var hash = window.location.hash.split("/");
    switch (hash[0]) {
    case "#narrow":
        ui.change_tab_to("#home");
        var operators = parse_narrow(hash);
        if (operators === undefined) {
            // If the narrow URL didn't parse, clear
            // window.location.hash and send them to the home tab
            set_hash('');
            activate_home_tab();
            return false;
        }
        var narrow_opts = {
            select_first_unread: true,
            change_hash:    false,  // already set
            trigger: 'hash change'
        };
        if (from_reload !== undefined && page_params.initial_narrow_pointer !== undefined) {
            narrow_opts.from_reload = true;
            narrow_opts.first_unread_from_server = true;
        }
        narrow.activate(operators, narrow_opts);
        floating_recipient_bar.update();
        return true;
    case "":
    case "#":
        activate_home_tab();
        break;
    case "#subscriptions":
        ui.change_tab_to("#subscriptions");
        break;
    case "#administration":
        ui.change_tab_to("#administration");
        break;
    case "#settings":
        ui.change_tab_to("#settings");
        break;
    }
    return false;
}

function hashchanged(from_reload) {
    changing_hash = true;
    var ret = do_hashchange(from_reload);
    changing_hash = false;
    return ret;
}

exports.initialize = function () {
    // jQuery doesn't have a hashchange event, so we manually wrap
    // our event handler
    window.onhashchange = blueslip.wrap_function(hashchanged);
    hashchanged(true);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = hashchange;
}
