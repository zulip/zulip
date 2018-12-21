var feedback_widget = (function () {

var exports = {};

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


var meta = {
    hide_me_time: null,
    alert_hover_state: false,
    $container: null,
    opened: false,
};

var animate = {
    maybe_close: function () {
        if (!meta.opened) {
            return;
        }

        if (meta.hide_me_time < new Date().getTime() && !meta.alert_hover_state) {
            animate.fadeOut();
            return;
        }

        setTimeout(animate.maybe_close, 100);
    },
    fadeOut: function () {
        if (!meta.opened) {
            return;
        }

        if (meta.$container) {
            meta.$container.fadeOut(500).removeClass("show");
            meta.opened = false;
            meta.alert_hover_state = false;
        }
    },
    fadeIn: function () {
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
    meta.$container.mouseenter(function () {
        if (!meta.opened) {
            return;
        }

        meta.alert_hover_state = true;
    });

    // once the user's mouse leaves the notification, restart the countdown.
    meta.$container.mouseleave(function () {
        if (!meta.opened) {
            return;
        }

        meta.alert_hover_state = false;
        // add at least 2000ms but if more than that exists just keep the
        // current amount.
        meta.hide_me_time = Math.max(meta.hide_me_time, new Date().getTime() + 2000);
    });

    meta.$container.on('click', '.exit-me', function () {
        animate.fadeOut();
    });

    meta.$container.on('click', '.feedback_undo', function () {
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
        blueslip.error('programmer needs to supply populate callback.');
        return;
    }

    meta.$container = $('#feedback_container');

    var html = templates.render('feedback_container');
    meta.$container.html(html);

    set_up_handlers();

    meta.undo = opts.on_undo;

    // add a four second delay before closing up.
    meta.hide_me_time = new Date().getTime() + 4000;

    meta.$container.find('.feedback_title').text(opts.title_text);
    meta.$container.find('.feedback_undo').text(opts.undo_button_text);
    opts.populate(meta.$container.find('.feedback_content'));

    animate.fadeIn();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = feedback_widget;
}
window.feedback_widget = feedback_widget;
