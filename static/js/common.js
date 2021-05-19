import $ from "jquery";
import tippy from "tippy.js";

import {$t} from "./i18n";

export const status_classes = "alert-error alert-success alert-info alert-warning";

// TODO: Move this to the portico codebase.
export function autofocus(selector) {
    $(() => {
        $(selector).trigger("focus");
    });
}

export function phrase_match(query, phrase) {
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
}

export function copy_data_attribute_value(elem, key) {
    // function to copy the value of data-key
    // attribute of the element to clipboard
    const temp = $(document.createElement("input"));
    $("body").append(temp);
    temp.val(elem.data(key)).trigger("select");
    document.execCommand("copy");
    temp.remove();
    elem.fadeOut(250);
    elem.fadeIn(1000);
}

export function has_mac_keyboard() {
    return /mac/i.test(navigator.platform);
}

export function adjust_mac_shortcuts(key_elem_class, require_cmd_style) {
    if (!has_mac_keyboard()) {
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
}

// See https://zulip.readthedocs.io/en/latest/development/authentication.html#password-form-implementation
// for design details on this feature.
function set_password_toggle_label(password_selector, label, tippy_tooltips) {
    $(password_selector).attr("aria-label", label);
    if (tippy_tooltips) {
        if (!$(password_selector)[0]._tippy) {
            tippy(password_selector);
        }
        $(password_selector)[0]._tippy.setContent(label);
    } else {
        $(password_selector).attr("title", label);
    }
}

function toggle_password_visibility(password_field_id, password_selector, tippy_tooltips) {
    let label;
    const password_field = $(password_field_id);

    if (password_field.attr("type") === "password") {
        password_field.attr("type", "text");
        $(password_selector).removeClass("fa-eye-slash").addClass("fa-eye");
        label = $t({defaultMessage: "Hide password"});
    } else {
        password_field.attr("type", "password");
        $(password_selector).removeClass("fa-eye").addClass("fa-eye-slash");
        label = $t({defaultMessage: "Show password"});
    }
    set_password_toggle_label(password_selector, label, tippy_tooltips);
}

export function reset_password_toggle_icons(password_field, password_selector) {
    $(password_field).attr("type", "password");
    $(password_selector).removeClass("fa-eye").addClass("fa-eye-slash");
    const label = $t({defaultMessage: "Show password"});
    set_password_toggle_label(password_selector, label, true);
}

export function setup_password_visibility_toggle(password_field_id, password_selector, opts = {}) {
    opts = {tippy_tooltips: false, ...opts};
    const label = $t({defaultMessage: "Show password"});
    set_password_toggle_label(password_selector, label, opts.tippy_tooltips);
    $(password_selector).on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggle_password_visibility(password_field_id, password_selector, opts.tippy_tooltips);
    });
}
