var muting_ui = (function () {

var exports = {};

function timestamp_ms() {
    return (new Date()).getTime();
}

var last_topic_update = 0;

exports.rerender = function () {
    stream_list.update_streams_sidebar();
    current_msg_list.rerender_after_muting_changes();
    if (current_msg_list !== home_msg_list) {
        home_msg_list.rerender_after_muting_changes();
    }
};

exports.notify_with_undo_option = (function () {
    var meta = {
        stream: null,
        topic: null,
        hide_me_time: null,
        alert_hover_state: false,
        $mute: null
    };
    var animate = {
        fadeOut: function () {
            if (meta.$mute) {
                meta.$mute.fadeOut(500).removeClass("show");
            }
        },
        fadeIn: function () {
            if (meta.$mute) {
                meta.$mute.fadeIn(500).addClass("show");
            }
        }
    };
    setInterval(function () {
        if (meta.hide_me_time < new Date().getTime() && !meta.alert_hover_state) {
            animate.fadeOut();
        }
    }, 100);

    return function (stream, topic) {
        var $exit = $("#unmute_muted_topic_notification .exit-me");

        if (!meta.$mute) {
          meta.$mute = $("#unmute_muted_topic_notification");

          $exit.click(function () {
              animate.fadeOut();
          });

          meta.$mute.find("#unmute").click(function () {
              // it should reference the meta variable and not get stuck with
              // a pass-by-value of stream, topic.
              popovers.topic_ops.unmute(meta.stream, meta.topic);
              animate.fadeOut();
          });
        }

        meta.stream = stream;
        meta.topic = topic;
        // add a four second delay before closing up.
        meta.hide_me_time = new Date().getTime() + 4000;

        meta.$mute.find(".topic").html(topic);
        meta.$mute.find(".stream").html(stream);

        animate.fadeIn();

        // if the user mouses over the notification, don't hide it.
        meta.$mute.mouseenter(function () {
            meta.alert_hover_state = true;
        });

        // once the user's mouse leaves the notification, restart the countdown.
        meta.$mute.mouseleave(function () {
            meta.alert_hover_state = false;
            // add at least 2000ms but if more than that exists just keep the
            // current amount.
            meta.hide_me_time = Math.max(meta.hide_me_time, new Date().getTime() + 2000);
        });
    };
}());

exports.persist_and_rerender = function () {
    // Optimistically rerender our new muting preferences.  The back
    // end should eventually save it, and if it doesn't, it's a recoverable
    // error--the user can just mute the topic again, and the topic might
    // die down before the next reload anyway, making the muting moot.
    exports.rerender();
    var data = {
        muted_topics: JSON.stringify(muting.get_muted_topics())
    };
    last_topic_update = timestamp_ms();
    channel.post({
        url: '/json/set_muted_topics',
        idempotent: true,
        data: data
    });
};

exports.handle_updates = function (muted_topics) {
    if (timestamp_ms() < last_topic_update + 1000) {
        // This topic update is either the one that we just rendered, or,
        // much less likely, it's coming from another device and would probably
        // be overwriting this device's preferences with stale data.
        return;
    }

    muting.set_muted_topics(muted_topics);
    exports.rerender();
};

$(function () {
    muting.set_muted_topics(page_params.muted_topics);
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = muting_ui;
}
