import $ from "jquery";

import render_feedback_container from "../templates/feedback_container.hbs";

import * as blueslip from "./blueslip";

/*

This code lets you show something like this:

    +-----
    | TOPIC MUTES [undo] [x]
    |
    | You muted stream Foo, topic Bar.
    +-----

And then you configure the undo behavior, and
everything else is controlled by the widget.

Code-wise it's a singleton widget that controls the DOM inside
#feedback_container, which gets served up by server.

*/

type FeedbackWidgetMeta = {
    hide_me_time: number | null;
    alert_hover_state: boolean;
    $container: JQuery | null;
    opened: boolean;
    handlers_set?: boolean;
    undo?: () => void;
};

type FeedbackWidgetOptions = {
    populate: (element: JQuery) => void;
    title_text: string;
    undo_button_text: string;
    on_undo: () => void;
};

const meta: FeedbackWidgetMeta = {
    hide_me_time: null,
    alert_hover_state: false,
    $container: null,
    opened: false,
};

const animate = {
    maybe_close() {
        if (!meta.opened) {
            return;
        }

        if ((meta.hide_me_time ?? 0) < Date.now() && !meta.alert_hover_state) {
            animate.fadeOut();
            return;
        }

        setTimeout(() => animate.maybe_close(), 100);
    },
    fadeOut() {
        if (!meta.opened) {
            return;
        }

        if (meta.$container) {
            meta.$container.addClass("slide-out-feedback-container");
            // Delay setting `display: none` enough that the hide animation starts.
            setTimeout(
                () =>
                    meta.$container?.removeClass([
                        "show-feedback-container",
                        "slide-out-feedback-container",
                    ]),
                50,
            );
            meta.opened = false;
            meta.alert_hover_state = false;
        }
    },
    fadeIn() {
        if (meta.opened) {
            return;
        }

        if (meta.$container) {
            meta.$container.addClass("show-feedback-container");
            meta.opened = true;
            setTimeout(() => animate.maybe_close(), 100);
        }
    },
};

function set_up_handlers(): void {
    if (meta.handlers_set) {
        return;
    }

    if (!meta.$container) {
        blueslip.error("$container not found for feedback widget.");
        return;
    }

    meta.handlers_set = true;

    // if the user mouses over the notification, don't hide it.
    meta.$container.on("mouseenter", () => {
        if (!meta.opened) {
            return;
        }

        meta.alert_hover_state = true;
    });

    // once the user's mouse leaves the notification, restart the countdown.
    meta.$container.on("mouseleave", () => {
        if (!meta.opened) {
            return;
        }

        meta.alert_hover_state = false;
        // add at least 2000ms but if more than that exists just keep the
        // current amount.
        meta.hide_me_time = Math.max(meta.hide_me_time ?? 0, Date.now() + 2000);
    });

    meta.$container.on("click", ".exit-me", () => {
        animate.fadeOut();
    });

    meta.$container.on("click", ".feedback_undo", () => {
        if (meta.undo) {
            meta.undo();
        }
        animate.fadeOut();
    });
}

export function is_open(): boolean {
    return meta.opened;
}

export function dismiss(): void {
    animate.fadeOut();
}

export function show(opts: FeedbackWidgetOptions): void {
    if (!opts.populate) {
        blueslip.error("programmer needs to supply populate callback.");
        return;
    }

    meta.$container = $("#feedback_container");

    const html = render_feedback_container({});
    meta.$container.html(html);

    set_up_handlers();

    meta.undo = opts.on_undo;

    // add a four second delay before closing up.
    meta.hide_me_time = Date.now() + 4000;

    meta.$container.find(".feedback_title").text(opts.title_text);
    meta.$container.find(".feedback_undo").text(opts.undo_button_text);
    opts.populate(meta.$container.find(".feedback_content"));

    animate.fadeIn();
}
