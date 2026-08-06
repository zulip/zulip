/*
    See hotkey.ts for handlers that are more app-wide.
*/

import * as common from "./common.ts";

export const vim_left = "h";
export const vim_down = "j";
export const vim_up = "k";
export const vim_right = "l";

export function handle(opts: {
    $elem: JQuery;
    handlers: Record<string, ((e?: JQuery.KeyDownEvent) => boolean) | undefined>;
}): void {
    opts.$elem.on("keydown", (e) => {
        if (e.altKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        const {key} = e;
        const handler = opts.handlers[key];
        if (!handler) {
            return;
        }

        const handled = handler(e);
        if (handled) {
            e.preventDefault();
            e.stopPropagation();
        }
    });
}

export function get_mac_ctrl_navigation_key(
    event: JQuery.KeyboardEventBase,
): "ArrowUp" | "ArrowDown" | undefined {
    if (
        !common.has_mac_keyboard() ||
        !event.ctrlKey ||
        event.altKey ||
        event.metaKey ||
        event.shiftKey
    ) {
        return undefined;
    }

    if (event.key.toLowerCase() === "n" || event.code === "KeyN") {
        return "ArrowDown";
    }

    if (event.key.toLowerCase() === "p" || event.code === "KeyP") {
        return "ArrowUp";
    }

    return undefined;
}

export function is_enter_event(event: JQuery.KeyboardEventBase): boolean {
    // In addition to checking whether the key pressed was an Enter
    // key, we need to check whether the keypress was part of an IME
    // composing session, such as selecting a character using a
    // phonetic input method like ZhuYin in a character-based
    // language. See #22062 for details. Further reading:
    // https://developer.mozilla.org/en-US/docs/Glossary/Input_method_editor
    const isComposing = event.originalEvent?.isComposing ?? false;
    return !isComposing && event.key === "Enter";
}
