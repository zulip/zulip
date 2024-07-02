import * as tippy from "tippy.js";

import {$t} from "./i18n";

export function show_copied_confirmation(
    copy_button: HTMLElement,
    on_hide_callback?: () => void,
    timeout_in_ms = 1000,
): void {
    // Display a tooltip to notify the user the message or code was copied.
    const instance = tippy.default(copy_button, {
        placement: "top",
        appendTo: () => document.body,
        onUntrigger() {
            remove_instance();
        },
        onHide() {
            if (on_hide_callback) {
                on_hide_callback();
            }
        },
    });
    instance.setContent($t({defaultMessage: "Copied!"}));
    instance.show();
    function remove_instance(): void {
        if (!instance.state.isDestroyed) {
            instance.destroy();
        }
    }
    setTimeout(remove_instance, timeout_in_ms);
}
