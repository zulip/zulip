import {$} from "jquery";

import * as util from "./util.ts";

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
// the trigger (e.g. a reaction pill, a buddy list row, or a user pill),
// add the class `emoji-animation-hover-area` to that ancestor.

const ANIMATED_EMOJI_SELECTOR = "img.emoji[data-animated-url]";
const ANIMATION_TRIGGER_SELECTOR = `.emoji-animation-hover-area, ${ANIMATED_EMOJI_SELECTOR}`;

function animated_emojis_for_trigger($trigger: JQuery): JQuery {
    return $trigger.is(".emoji-animation-hover-area")
        ? $trigger.find(ANIMATED_EMOJI_SELECTOR)
        : $trigger;
}

function is_owned_by_hover_area($trigger: JQuery): boolean {
    // An ancestor hover area receives its own events for the same
    // pointer movement, so letting an emoji inside one drive itself as
    // well would just do the work twice.
    return (
        $trigger.is(ANIMATED_EMOJI_SELECTOR) &&
        $trigger.closest(".emoji-animation-hover-area").length > 0
    );
}

function should_animate($trigger: JQuery): boolean {
    // We consult the setting here rather than trusting the rendered markup,
    // since most surfaces aren't rerendered when the setting changes.
    const animation_setting = util.effective_web_animate_image_previews();
    if (animation_setting !== "on_hover") {
        return animation_setting === "always";
    }

    // A trigger can be hovered and focused at the same time, so recompute
    // from both states rather than tracking the enter/leave and
    // focus/blur transitions separately; otherwise moving the mouse off a
    // keyboard-focused trigger would stop its animation.
    //
    // We check `:focus-visible` so that only keyboard focus counts, since a
    // mouse click can leave focus on a trigger after the mouse has moved
    // away. We also check descendants because a hover area is often not
    // focusable itself while wrapping something that is, such as the buddy
    // list row around its user link.
    return (
        $trigger.is(":hover") ||
        $trigger.is(":focus-visible") ||
        $trigger.find(":focus-visible").length > 0
    );
}

function update_animation_state($trigger: JQuery): void {
    const attr = should_animate($trigger) ? "data-animated-url" : "data-still-url";
    animated_emojis_for_trigger($trigger).each(function () {
        const url = $(this).attr(attr);
        if (url !== undefined) {
            $(this).attr("src", url);
        }
    });
}

export function update_all_rendered_emojis(): void {
    // Most surfaces aren't rerendered when the setting changes, so bring
    // the emojis they show up to date here.
    $(ANIMATED_EMOJI_SELECTOR).each(function () {
        update_animation_state($(this));
    });
}

export function initialize(): void {
    $("body").on(
        "mouseenter mouseleave focusin focusout",
        ANIMATION_TRIGGER_SELECTOR,
        function (this: HTMLElement) {
            const $trigger = $(this);
            if (is_owned_by_hover_area($trigger)) {
                return;
            }
            update_animation_state($trigger);
        },
    );
}
