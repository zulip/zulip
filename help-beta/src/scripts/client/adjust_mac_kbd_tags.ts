// Any changes to this file should be followed by a check for changes
// needed to make to adjust_mac_kbd_tags of web/src/common.ts.

const keys_map = new Map<string, string>([
    ["Backspace", "Delete"],
    ["Enter", "Return"],
    ["Ctrl", "⌘"],
    ["Alt", "⌥"],
]);

function has_mac_keyboard(): boolean {
    "use strict";

    // eslint-disable-next-line @typescript-eslint/no-deprecated
    return /mac/i.test(navigator.platform);
}

// We convert the <kbd> tags used for keyboard shortcuts to mac equivalent
// key combinations, when we detect that the user is using a mac-style keyboard.
function adjust_mac_kbd_tags(): void {
    "use strict";

    if (!has_mac_keyboard()) {
        return;
    }

    const elements = document.querySelectorAll<HTMLElement>("kbd");

    for (const element of elements) {
        let key_text: string = element.textContent ?? "";

        // We use data-mac-key attribute to override the default key in case
        // of exceptions:
        // - There are 2 shortcuts (for navigating back and forth in browser
        //   history) which need "⌘" instead of the expected mapping ("Opt")
        //   for the "Alt" key, so we use this attribute to override "Opt"
        //   with "⌘".
        // - The "Ctrl" + "[" shortcuts (which match the Vim keybinding behavior
        //   of mapping to "Esc") need to display "Ctrl" for all users, so we
        //   use this attribute to override "⌘" with "Ctrl".
        const replace_key: string | undefined = element.dataset.macKey ?? keys_map.get(key_text);
        if (replace_key !== undefined) {
            key_text = replace_key;
        }

        element.textContent = key_text;

        // In case of shortcuts, the Mac equivalent of which involves extra keys,
        // we use data-mac-following-key attribute to append the extra key to the
        // previous key. Currently, this is used to append Opt to Cmd for the Paste
        // as plain text shortcut.
        const following_key: string | undefined = element.dataset.macFollowingKey;
        if (following_key !== undefined) {
            const kbd_elem: HTMLElement = document.createElement("kbd");
            kbd_elem.textContent = following_key;
            element.after(kbd_elem);
            element.after(" + ");
        }

        // In web/src/common.ts, we use zulip icon for ⌘ due to centering
        // problems, we don't have that problem in the new help center and
        // thus don't do that transformation here. We do need to make these
        // symbols appear larger than they do by default since they are too
        // small to see in the default font-size.
        if (key_text === "⌘" || key_text === "⌥") {
            element.style.fontSize = "1.5em";
            element.style.verticalAlign = "middle";
        }
    }
}

adjust_mac_kbd_tags();
