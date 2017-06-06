// Read https://zulip.readthedocs.io/en/latest/hashchange-system.html
var hashchange = (function () {

var exports = {};

var changing_hash = false;

function set_hash(hash) {
    var location = window.location;

    if (history.pushState && util.is_unsupported_ie()) {
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
    $(document).trigger($.Event('zuliphashchange.zulip'));
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
            hash += '/' + sign + hash_util.encodeHashComponent(operator)
                  + '/' + hash_util.encode_operand(operator, operand);
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

exports.parse_narrow = function (hash) {
    var i;
    var operators = [];
    for (i = 1; i < hash.length; i += 2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        try {
            var operator = hash_util.decodeHashComponent(hash[i].component);
            var operand  = hash_util.decode_operand(operator, hash[i + 1].component || '');
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
};

function activate_home_tab() {
    ui_util.change_tab_to("#home");
    narrow.deactivate();
    floating_recipient_bar.update();
}

var router = new Router();

router.use(function (e, next) {
    $(document).trigger($.Event('zuliphashchange.zulip'));
    next();
});

router.add("keyboard-shortcuts", function () {
    ui.show_info_overlay("keyboard-shortcuts");
});

router.add("markdown-help", function () {
    ui.show_info_overlay("markdown-help");
});

router.add("search-operators", function () {
    ui.show_info_overlay("search-operators");
});

router.add(["streams/*", "streams"], function (e) {
    ui_util.change_tab_to("#streams");
    subs.launch(router.parse(e.hash));
});

router.add("invite", function () {
    invite.initialize();
});

router.add("", function () {
    activate_home_tab();
});

router.add("settings", function () {
    window.location.hash = "#settings/your-account";
});

router.add("organization", function () {
    window.location.hash = "#organization/organization-settings";
});

router.add("settings/:key", function () {
    ui_util.change_tab_to("#settings");
    if (!overlays.settings_open()) {
        settings.setup_page();
        admin.setup_page();
    }
});

router.add("organization/:key", function () {
    ui_util.change_tab_to("#organization");
    if (!overlays.settings_open()) {
        settings.setup_page();
        admin.setup_page();
    }
});

router.add("drafts", function () {
    ui_util.change_tab_to("#drafts");
    drafts.launch();
});

router.add("narrow/*", function (e) {
    var operators = exports.parse_narrow(router.parse(e.hash));
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
        trigger: 'hash change',
    };
    if (e.initial_load && page_params.initial_narrow_pointer !== undefined) {
        narrow_opts.from_reload = true;
        narrow_opts.first_unread_from_server = true;
    }
    narrow.activate(operators, narrow_opts);
    floating_recipient_bar.update();
});

function should_ignore(hash) {
    // Hash changes within this list are overlays and should not unnarrow (etc.)
    var ignore_list = ["streams", "drafts", "settings", "organization", "invite"];
    var main_hash = router.parse(hash)[0].component;

    return (ignore_list.indexOf(main_hash) > -1);
}

exports.initialize = router.init.bind(router);

exports.exit_overlay = function (callback) {
    for (var x = router.history.length - 1; x >= 0; x -= 1) {
        if (!should_ignore(router.history[x])) {
            ui_util.blur_active_element();
            window.location.hash = router.history[x];
            if (typeof callback === "function") {
                callback();
            }

            return;
        }
    }

    window.location.hash = "#";
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = hashchange;
}
