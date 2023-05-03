/* eslint-disable @typescript-eslint/unbound-method */

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

const meta: {
    hide_me_time: number;
    alert_hover_state: boolean;
    $container?: JQuery;
    opened: boolean;
    handlers_set?: boolean;
    undo?: () => void;
} = {
    hide_me_time: 0,
    alert_hover_state: false,
    $container: undefined,
    opened: false,
};

const animate = {
    maybe_close() {
        if (!meta.opened) {
            return;
        }

        if (meta.hide_me_time < Date.now() && !meta.alert_hover_state) {
            animate.fadeOut();
            return;
        }

        setTimeout(animate.maybe_close, 100);
    },
    fadeOut(): void {
        if (meta.opened === undefined) {
            return;
        }

        if (meta.$container !== undefined) {
            meta.$container.fadeOut(500).removeClass("show");
            meta.opened = false;
            meta.alert_hover_state = false;
        }
    },
    fadeIn(): void {
        if (meta.opened) {
            return;
        }

        if (meta.$container !== undefined) {
            meta.$container.fadeIn(500).addClass("show");
            meta.opened = true;
            setTimeout(animate.maybe_close, 100);
        }
    },
};

function set_up_handlers(): void {
    if (meta.handlers_set !== undefined) {
        return;
    }

    meta.handlers_set = true;
    if (meta.$container === undefined) {
        return;
    }

    // if the user mouses over the notification, don't hide it.

    meta.$container.on("mouseenter", () => {
        if (meta.opened === undefined) {
            return;
        }

        meta.alert_hover_state = true;
    });

    // once the user's mouse leaves the notification, restart the countdown.

    meta.$container.on("mouseleave", () => {
        if (meta.opened === undefined) {
            return;
        }

        meta.alert_hover_state = false;
        // add at least 2000ms but if more than that exists just keep the
        // current amount.
        meta.hide_me_time = Math.max(meta.hide_me_time, Date.now() + 2000);
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

export function show(opts: {
    title_text: string;
    undo_button_text: string;
    populate: (container: JQuery) => void;
    on_undo: () => void;
}): void {
    if (opts.populate === undefined) {
        blueslip.error("programmer needs to supply populate callback.");
        return;
    }

    meta.$container = $("#feedback_container");

    const html = render_feedback_container();
    if (meta.$container?.html !== undefined) {
        meta.$container.html(html);
    }

    set_up_handlers();

    meta.undo = opts.on_undo;

    // add a four second delay before closing up.
    meta.hide_me_time = Date.now() + 4000;
    if (meta.$container !== undefined) {
        meta.$container.find(".feedback_title").text(opts.title_text);
        meta.$container.find(".feedback_undo").text(opts.undo_button_text);
        opts.populate(meta.$container.find(".feedback_content"));

        animate.fadeIn();
    }
}
