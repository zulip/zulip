// Read https://zulip.readthedocs.io/en/latest/subsystems/hashchange-system.html
var hashchange = (function () {

var exports = {};

var expected_hash;
var changing_hash = false;

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
    $(document).trigger($.Event('zuliphashchange.zulip'));
    set_hash(newhash);
    favicon.reset();
};

exports.save_narrow = function (operators) {
    if (changing_hash) {
        return;
    }
    var new_hash = hash_util.operators_to_hash(operators);
    exports.changehash(new_hash);
};

exports.parse_narrow = function (hash) {
    var i;
    var operators = [];
    for (i = 1; i < hash.length; i += 2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        try {
            var operator = hash_util.decodeHashComponent(hash[i]);
            // Do not parse further if empty operator encountered.
            if (operator === '') {
                break;
            }

            var operand  = hash_util.decode_operand(operator, hash[i + 1] || '');
            var negated = false;
            if (operator[0] === '-') {
                negated = true;
                operator = operator.slice(1);
            }
            operators.push({negated: negated, operator: operator, operand: operand});
        } catch (err) {
            return;
        }
    }
    return operators;
};

function activate_home_tab() {
    ui_util.change_tab_to("#home");
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
        expected_hash !== undefined &&
         window.location.hash.replace(/^#/, '') === '' &&
         expected_hash.replace(/^#/, '') === '') {
        return false;
    }

    $(document).trigger($.Event('zuliphashchange.zulip'));

    // NB: In Firefox, window.location.hash is URI-decoded.
    // Even if the URL bar says #%41%42%43%44, the value here will
    // be #ABCD.
    var hash = window.location.hash.split("/");
    switch (hash[0]) {
    case "#narrow":
        ui_util.change_tab_to("#home");
        var operators = exports.parse_narrow(hash);
        if (operators === undefined) {
            // If the narrow URL didn't parse, clear
            // window.location.hash and send them to the home tab
            set_hash('');
            activate_home_tab();
            return false;
        }
        var narrow_opts = {
            change_hash:    false,  // already set
            trigger: 'hash change',
        };
        if (from_reload) {
            blueslip.debug('We are narrowing as part of a reload.');
            if (page_params.initial_narrow_pointer !== undefined) {
                home_msg_list.pre_narrow_offset = page_params.initial_offset;
                narrow_opts.then_select_id = page_params.initial_narrow_pointer;
                narrow_opts.then_select_offset = page_params.initial_narrow_offset;
            }
        }
        narrow.activate(operators, narrow_opts);
        floating_recipient_bar.update();
        return true;
    case "":
    case "#":
        activate_home_tab();
        break;
    case "#streams":
        ui_util.change_tab_to("#streams");
        break;
    case "#keyboard-shortcuts":
        info_overlay.show("keyboard-shortcuts");
        break;
    case "#message-formatting":
        info_overlay.show("message-formatting");
        break;
    case "#search-operators":
        info_overlay.show("search-operators");
        break;
    case "#drafts":
        ui_util.change_tab_to("#drafts");
        break;
    case "#organization":
        ui_util.change_tab_to("#organization");
        break;
    case "#settings":
        ui_util.change_tab_to("#settings");
        break;
    }
    return false;
}

// -- -- -- -- -- -- READ THIS BEFORE TOUCHING ANYTHING BELOW -- -- -- -- -- -- //
// HOW THE HASH CHANGE MECHANISM WORKS:
// When going from a normal view (eg. `narrow/is/private`) to a settings panel
// (eg. `settings/your-bots`) it should trigger the `is_overlay_hash` function and
// return `true` for the current state -- we want to ignore hash changes from
// within the settings page. The previous hash however should return `false` as it
// was outside of the scope of settings.
// there is then an `exit_overlay` function that allows the hash to change exactly
// once without triggering any events. This allows the hash to reset back from
// a settings page to the previous view available before the settings page
// (eg. narrow/is/private). This saves the state, scroll position, and makes the
// hash change functionally inert.
// -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- - -- //
var ignore = {
    is_exiting_overlay: false,
    hash_before_overlay: null,
    old_hash: typeof window !== "undefined" ? window.location.hash : "#",
    group: null,
};

function get_main_hash(hash) {
    return hash ? hash.replace(/^#/, "").split(/\//)[0] : "";
}

function get_hash_components() {
    var hash = window.location.hash.split(/\//);

    return {
        base: hash.shift(),
        arguments: hash,
    };
}

// different groups require different reloads. The grouped elements don't
// require a reload or overlay change to run.
var get_hash_group = (function () {
    var groups = [
        ["streams"],
        ["settings", "organization"],
        ["invite"],
    ];

    return function (value) {
        var idx = null;

        _.find(groups, function (o, i) {
            if (o.indexOf(value) !== -1) {
                idx = i;
                return true;
            }
            return false;
        });

        return idx;
    };
}());

function is_overlay_hash(hash) {
    // Hash changes within this list are overlays and should not unnarrow (etc.)
    var overlay_list = ["streams", "drafts", "settings", "organization", "invite"];
    var main_hash = get_main_hash(hash);

    return overlay_list.indexOf(main_hash) > -1;
}

function hashchanged_overlay(old_hash) {
    var base = get_main_hash(window.location.hash);

    // if the old has was a standard non-ignore hash OR the ignore hash
    // base has changed, something needs to run again.

    if (!is_overlay_hash(old_hash || "#") || ignore.group !== get_hash_group(base)) {
        if (ignore.group !== get_hash_group(base)) {
            overlays.close_for_hash_change();
        }

        // now only if the previous one should not have been ignored.
        if (!is_overlay_hash(old_hash || "#")) {
            ignore.hash_before_overlay = old_hash;
        }

        if (base === "streams") {
            subs.launch(get_hash_components());
        } else if (base === "drafts") {
            drafts.launch();
        } else if (/settings|organization/.test(base)) {
            settings.setup_page();
            admin.setup_page();
        } else if (base === "invite") {
            invite.launch();
        }

        ignore.group = get_hash_group(base);
    } else {
        subs.change_state(get_hash_components());
    }
}

function hashchanged(from_reload, e) {
    var old_hash;
    if (e) {
        old_hash = "#" + (e.oldURL || ignore.old_hash).split(/#/).slice(1).join("");
        ignore.old_hash = window.location.hash;
    }

    if (is_overlay_hash(window.location.hash)) {
        hashchanged_overlay(old_hash);
    } else if (!ignore.is_exiting_overlay) {
        overlays.close_for_hash_change();
        changing_hash = true;
        var ret = do_hashchange(from_reload);
        changing_hash = false;
        return ret;
    // once we unignore the hash, we have to set the hash back to what it was
    // originally (eg. '#narrow/stream/999-Denmark' instead of '#settings'). We
    // therefore ignore the hash change once more while we change it back for
    // no interruptions.
    } else if (ignore.is_exiting_overlay) {
        ignore.is_exiting_overlay = false;
    }
}

exports.initialize = function () {
    // jQuery doesn't have a hashchange event, so we manually wrap
    // our event handler
    window.onhashchange = blueslip.wrap_function(function (e) {
        hashchanged(false, e);
    });
    hashchanged(true);
};

exports.exit_overlay = function (callback) {
    if (is_overlay_hash(window.location.hash)) {
        ui_util.blur_active_element();
        ignore.is_exiting_overlay = true;
        window.location.hash = ignore.hash_before_overlay || "#";
        if (typeof callback === "function") {
            callback();
        }
    }
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = hashchange;
}
window.hashchange = hashchange;
