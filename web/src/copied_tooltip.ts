import $ from "jquery";
import * as tippy from "tippy.js";

import {$t} from "./i18n.ts";

function show_copied_tooltip(copy_button: Element, on_hide_callback?: () => void): tippy.Instance {
    // Display a tooltip to notify the user the message or code was copied.
    const instance = tippy.default(copy_button, {
        placement: "top",
        appendTo: () => document.body,
        onUntrigger(instance) {
            instance.destroy();
        },
        onHide() {
            if (on_hide_callback) {
                on_hide_callback();
            }
        },
    });
    instance.setContent($t({defaultMessage: "Copied!"}));
    instance.show();
    return instance;
}

function show_check_icon(copy_button: Element): void {
    $(copy_button).addClass("copy-button-success");
    $(copy_button).find(".zulip-icon").removeClass("zulip-icon-copy").addClass("zulip-icon-check");
}

function remove_check_icon(copy_button: Element): void {
    $(copy_button).removeClass("copy-button-success");
    $(copy_button).find(".zulip-icon").addClass("zulip-icon-copy").removeClass("zulip-icon-check");
}

export function show_copied_confirmation(
    copy_button: Element,
    opts?: {
        show_check_icon?: boolean;
        timeout_in_ms?: number;
        on_hide_callback?: () => void;
    },
): void {
    const instance = show_copied_tooltip(copy_button, opts?.on_hide_callback);
    if (opts?.show_check_icon) {
        show_check_icon(copy_button);
    }

    setTimeout(() => {
        if (!instance.state.isDestroyed) {
            instance.destroy();
        }
        if (opts?.show_check_icon) {
            remove_check_icon(copy_button);
        }
    }, opts?.timeout_in_ms ?? 1000);
}
