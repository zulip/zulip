import $ from "jquery";

// Drives the `on_hover` mode of the `web_animate_image_previews` setting
// for animated custom (realm) emojis.
//
// An animated emoji is rendered as a single `<img class="emoji">` whose
// `data-still-url` is its static (PNG) URL and `data-animated-url` is its
// animated (GIF/APNG) URL. Initial `src` is the still URL; this module
// swaps it to the animated URL while the hover area is hovered.
//
// The hover area is the emoji itself by default; to make a larger ancestor
// be the trigger (e.g. a reaction button or a buddy-list row), add the
// class `emoji-animation-hover-area` to that ancestor.

const HOVER_AREA_SELECTOR = ".emoji-animation-hover-area";
const SELF_TRIGGER_SELECTOR = "img.emoji[data-animated-url]";

function swap_emoji_src(
    $root: JQuery,
    attr: "data-animated-url" | "data-still-url",
): void {
    const $imgs = $root.is(SELF_TRIGGER_SELECTOR)
        ? $root
        : $root.find(SELF_TRIGGER_SELECTOR);
    $imgs.each(function () {
        const url = $(this).attr(attr);
        if (url !== undefined) {
            $(this).attr("src", url);
        }
    });
}

function ancestor_hover_area_handles(target: HTMLElement): boolean {
    // When the img itself fires mouseenter/leave but a `.emoji-animation-hover-area`
    // ancestor also fires, let the ancestor own the swap so we don't run twice.
    const $target = $(target);
    return $target.is(SELF_TRIGGER_SELECTOR) && $target.closest(HOVER_AREA_SELECTOR).length > 0;
}

export function initialize(): void {
    const selector = `${HOVER_AREA_SELECTOR}, ${SELF_TRIGGER_SELECTOR}`;
    $(document).on("mouseenter", selector, function () {
        if (ancestor_hover_area_handles(this)) {
            return;
        }
        swap_emoji_src($(this), "data-animated-url");
    });
    $(document).on("mouseleave", selector, function () {
        if (ancestor_hover_area_handles(this)) {
            return;
        }
        swap_emoji_src($(this), "data-still-url");
    });
}
