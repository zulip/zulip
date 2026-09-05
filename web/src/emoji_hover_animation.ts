import {$} from "jquery";

import {user_settings} from "./user_settings.ts";

// Drives the `on_hover` mode of the `web_animate_image_previews` setting
// for animated custom (realm) emojis.
//
// An animated emoji renders as a single `<img class="emoji">` whose
// `data-still-url` is its static (PNG) URL and `data-animated-url` its
// animated (GIF/APNG) URL, with the still URL as the initial `src`. We
// swap `src` to the animated URL while the emoji's trigger is hovered or
// keyboard-focused.
//
// The trigger is the emoji itself by default; to make a larger ancestor
// the trigger (e.g. a reaction pill, a buddy list row, or an emoji picker
// cell), add the class `emoji-animation-hover-area` to that ancestor.

const ANIMATION_TRIGGER_SELECTOR = ".emoji-animation-hover-area, img.emoji[data-animated-url]";

function animated_emojis_for_trigger($trigger: JQuery): JQuery {
    return $trigger.is(".emoji-animation-hover-area")
        ? $trigger.find("img.emoji[data-animated-url]")
        : $trigger;
}

function update_animation_state($trigger: JQuery): void {
    // A trigger can be hovered and focused at the same time, so recompute
    // from both states rather than tracking the enter/leave and
    // focus/blur transitions separately; otherwise moving the mouse off a
    // keyboard-focused trigger would stop its animation.
    //
    // We also consult the setting here rather than trusting the rendered
    // markup, so that a `data-animated-url` left behind by a stale render
    // can't animate an emoji the user asked to hold still.
    const attr =
        user_settings.web_animate_image_previews === "on_hover" &&
        ($trigger.is(":hover") || $trigger.is(":focus"))
            ? "data-animated-url"
            : "data-still-url";
    animated_emojis_for_trigger($trigger).each(function () {
        const url = $(this).attr(attr);
        if (url !== undefined) {
            $(this).attr("src", url);
        }
    });
}

export function initialize(): void {
    $("body").on(
        "mouseenter mouseleave focusin focusout",
        ANIMATION_TRIGGER_SELECTOR,
        function (this: HTMLElement) {
            const $trigger = $(this);
            if (
                $trigger.is("img.emoji[data-animated-url]") &&
                $trigger.closest(".emoji-animation-hover-area").length > 0
            ) {
                // An ancestor hover area owns this emoji, and receives its
                // own events for the same pointer movement, so letting the
                // emoji handle itself here would just do the work twice.
                return;
            }
            update_animation_state($trigger);
        },
    );
}
