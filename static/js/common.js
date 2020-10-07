"use strict";

// This reloads the module in development rather than refreshing the page
if (module.hot) {
    module.hot.accept();
}

exports.status_classes = "alert-error alert-success alert-info alert-warning";

exports.autofocus = function (selector) {
    $(() => {
        $(selector).trigger("focus");
    });
};

// Return a boolean indicating whether the password is acceptable.
// Also updates a Bootstrap progress bar control (a jQuery object)
// if provided.
//
// Assumes that zxcvbn.js has been loaded.
//
// This is in common.js because we want to use it from the signup page
// and also from the in-app password change interface.
exports.password_quality = function (password, bar, password_field) {
    // We load zxcvbn.js asynchronously, so the variable might not be set.
    if (typeof zxcvbn === "undefined") {
        return undefined;
    }

    const min_length = password_field.data("minLength");
    const min_guesses = password_field.data("minGuesses");

    const result = zxcvbn(password);
    const acceptable = password.length >= min_length && result.guesses >= min_guesses;

    if (bar !== undefined) {
        const t = result.crack_times_seconds.offline_slow_hashing_1e4_per_second;
        let bar_progress = Math.min(1, Math.log(1 + t) / 22);

        // Even if zxcvbn loves your short password, the bar should be
        // filled at most 1/3 of the way, because we won't accept it.
        if (!acceptable) {
            bar_progress = Math.min(bar_progress, 0.33);
        }

        // The bar bottoms out at 10% so there's always something
        // for the user to see.
        bar.width(90 * bar_progress + 10 + "%")
            .removeClass("bar-success bar-danger")
            .addClass(acceptable ? "bar-success" : "bar-danger");
    }

    return acceptable;
};

exports.password_warning = function (password, password_field) {
    if (typeof zxcvbn === "undefined") {
        return undefined;
    }

    const min_length = password_field.data("minLength");

    if (password.length < min_length) {
        return i18n.t("Password should be at least __length__ characters long", {
            length: min_length,
        });
    }
    return zxcvbn(password).feedback.warning || i18n.t("Password is too weak");
};

exports.phrase_match = function (query, phrase) {
    // match "tes" to "test" and "stream test" but not "hostess"
    let i;
    query = query.toLowerCase();

    phrase = phrase.toLowerCase();
    if (phrase.startsWith(query)) {
        return true;
    }

    const parts = phrase.split(" ");
    for (i = 0; i < parts.length; i += 1) {
        if (parts[i].startsWith(query)) {
            return true;
        }
    }
    return false;
};

exports.copy_data_attribute_value = function (elem, key) {
    // function to copy the value of data-key
    // attribute of the element to clipboard
    const temp = $(document.createElement("input"));
    $("body").append(temp);
    temp.val(elem.data(key)).trigger("select");
    document.execCommand("copy");
    temp.remove();
    elem.fadeOut(250);
    elem.fadeIn(1000);
};

exports.has_mac_keyboard = function () {
    return /mac/i.test(navigator.platform);
};

exports.adjust_mac_shortcuts = function (key_elem_class, require_cmd_style) {
    if (!exports.has_mac_keyboard()) {
        return;
    }

    const keys_map = new Map([
        ["Backspace", "Delete"],
        ["Enter", "Return"],
        ["Home", "Fn + ←"],
        ["End", "Fn + →"],
        ["PgUp", "Fn + ↑"],
        ["PgDn", "Fn + ↓"],
        ["Ctrl", "⌘"],
    ]);

    $(key_elem_class).each(function () {
        let key_text = $(this).text();
        const keys = key_text.match(/[^\s+]+/g) || [];

        if (key_text.includes("Ctrl") && require_cmd_style) {
            $(this).addClass("mac-cmd-key");
        }

        for (const key of keys) {
            if (keys_map.get(key)) {
                key_text = key_text.replace(key, keys_map.get(key));
            }
        }

        $(this).text(key_text);
    });
};

window.common = exports;
