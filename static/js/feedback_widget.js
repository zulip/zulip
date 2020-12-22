"use strict";

const render_feedback_container = require("../templates/feedback_container.hbs");

/*

This code lets you show something like this:

    +-----
    | TOPIC MUTES [undo] [x]
    |
    | You muted stream Foo, topic Bar.
    +-----

And then you configure the undo behavior, and
everything else is controlled by the widget.

Codewise it's a singleton widget that controls the DOM inside
#feedback_container, which gets served up by server.

*/

const meta = {
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

        if (meta.hide_me_time < Date.now() && !meta.alert_hover_state) {
            animate.fadeOut();
            return;
        }

        setTimeout(animate.maybe_close, 100);
    },
    fadeOut() {
        if (!meta.opened) {
            return;
        }

        if (meta.$container) {
            meta.$container.fadeOut(500).removeClass("show");
            meta.opened = false;
            meta.alert_hover_state = false;
        }
    },
    fadeIn() {
        if (meta.opened) {
            return;
        }

        if (meta.$container) {
            meta.$container.fadeIn(500).addClass("show");
            meta.opened = true;
            setTimeout(animate.maybe_close, 100);
        }
    },
};

function set_up_handlers() {
    if (meta.handlers_set) {
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

exports.is_open = function () {
    return meta.opened;
};

exports.dismiss = function () {
    animate.fadeOut();
};

exports.show = function (opts) {
    if (!opts.populate) {
        blueslip.error("programmer needs to supply populate callback.");
        return;
    }

    meta.$container = $("#feedback_container");

    const html = render_feedback_container();
    meta.$container.html(html);

    set_up_handlers();

    meta.undo = opts.on_undo;

    // add a four second delay before closing up.
    meta.hide_me_time = Date.now() + 4000;

    meta.$container.find(".feedback_title").text(opts.title_text);
    meta.$container.find(".feedback_undo").text(opts.undo_button_text);
    opts.populate(meta.$container.find(".feedback_content"));

    animate.fadeIn();
};

window.feedback_widget = exports;
