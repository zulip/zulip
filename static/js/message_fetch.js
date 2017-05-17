var message_fetch = (function () {

var exports = {};

// If the browser hasn't scrolled away from the top of the page
// since the last time that we ran load_more_messages(), we do
// not load_more_messages().
var load_more_enabled = true;

exports.reset_load_more_status = function reset_load_more_status() {
    load_more_enabled = true;
    ui.have_scrolled_away_from_top = true;
    ui.hide_loading_more_messages_indicator();
};

function process_result(messages, opts) {
    $('#connection-error').removeClass("show");

    if ((messages.length === 0) && (current_msg_list === message_list.narrowed) &&
        message_list.narrowed.empty()) {
        // Even after trying to load more messages, we have no
        // messages to display in this narrow.
        narrow.show_empty_narrow_message();
    }

    messages = _.map(messages, message_store.add_message_metadata);

    // If we're loading more messages into the home view, save them to
    // the message_list.all as well, as the home_msg_list is reconstructed
    // from message_list.all.
    if (opts.msg_list === home_msg_list) {
        message_util.do_unread_count_updates(messages);
        message_util.add_messages(messages, message_list.all, {messages_are_new: false});
    }

    if (messages.length !== 0 && !opts.cont_will_add_messages) {
        message_util.add_messages(messages, opts.msg_list, {messages_are_new: false});
    }

    activity.process_loaded_messages(messages);
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();

    if (opts.cont !== undefined) {
        opts.cont(messages);
    }
}

function get_old_messages_success(data, opts) {
    if (tutorial.is_running()) {
        // Don't actually process the messages until the tutorial is
        // finished, but do disable the loading indicator so it isn't
        // distracting in the background
        loading.destroy_indicator($('#page_loading_indicator'));
        tutorial.defer(function () { get_old_messages_success(data, opts); });
        return;
    }

    if (opts.msg_list.narrowed && opts.msg_list !== current_msg_list) {
        // We unnarrowed before receiving new messages so
        // don't bother processing the newly arrived messages.
        return;
    }
    if (! data) {
        // The server occationally returns no data during a
        // restart.  Ignore those responses and try again
        setTimeout(function () {
            exports.load_old_messages(opts);
        }, 0);
        return;
    }

    process_result(data.messages, opts);
    resize.resize_bottom_whitespace();
}


exports.load_old_messages = function load_old_messages(opts) {
    opts = _.extend({cont_will_add_messages: false}, opts);

    var data = {anchor: opts.anchor,
                num_before: opts.num_before,
                num_after: opts.num_after};

    if (opts.msg_list.narrowed && narrow_state.active()) {
        var operators = narrow_state.public_operators();
        if (page_params.narrow !== undefined) {
            operators = operators.concat(page_params.narrow);
        }
        data.narrow = JSON.stringify(operators);
    }
    if (opts.msg_list === home_msg_list && page_params.narrow_stream !== undefined) {
        data.narrow = JSON.stringify(page_params.narrow);
    }
    if (opts.use_first_unread_anchor) {
        data.use_first_unread_anchor = true;
    }

    channel.get({
        url:      '/json/messages',
        data:     data,
        idempotent: true,
        success: function (data) {
            get_old_messages_success(data, opts);
        },
        error: function (xhr) {
            if (opts.msg_list.narrowed && opts.msg_list !== current_msg_list) {
                // We unnarrowed before getting an error so don't
                // bother trying again or doing further processing.
                return;
            }
            if (xhr.status === 400) {
                // Bad request: We probably specified a narrow operator
                // for a nonexistent stream or something.  We shouldn't
                // retry or display a connection error.
                //
                // FIXME: Warn the user when this has happened?
                process_result([], opts);
                return;
            }

            // We might want to be more clever here
            $('#connection-error').addClass("show");
            setTimeout(function () {
                exports.load_old_messages(opts);
            }, 5000);
        },
    });
};


exports.load_more_messages = function load_more_messages(msg_list) {
    var batch_size = 100;
    var oldest_message_id;
    if (!load_more_enabled) {
        return;
    }
    ui.show_loading_more_messages_indicator();
    load_more_enabled = false;
    if (msg_list.first() === undefined) {
        oldest_message_id = page_params.pointer;
    } else {
        oldest_message_id = msg_list.first().id;
    }
    exports.load_old_messages({
        anchor: oldest_message_id.toFixed(),
        num_before: batch_size,
        num_after: 0,
        msg_list: msg_list,
        cont: function (messages) {
            ui.hide_loading_more_messages_indicator();
            if (messages.length >= batch_size) {
                load_more_enabled = true;
            }
        },
    });
};

util.execute_early(function () {
    // get the initial message list
    function load_more(messages) {

        // If we received the initially selected message, select it on the client side,
        // but not if the user has already selected another one during load.
        //
        // We fall back to the closest selected id, as the user may have removed
        // a stream from the home before already
        if (home_msg_list.selected_id() === -1 && !home_msg_list.empty()) {
            home_msg_list.select_id(page_params.pointer,
                                    {then_scroll: true, use_closest: true,
                                     target_scroll_offset: page_params.initial_offset});
        }

        // catch the user up
        if (messages.length !== 0) {
            var latest_id = messages[messages.length-1].id;
            if (latest_id < page_params.max_message_id) {
                exports.load_old_messages({
                    anchor: latest_id.toFixed(),
                    num_before: 0,
                    num_after: 1000,
                    msg_list: home_msg_list,
                    cont: load_more,
                });
                return;
            }
        }

        server_events.home_view_loaded();

        // backfill more messages after the user is idle
        var backfill_batch_size = 1000;
        $(document).idle({idle: 1000*10,
                          onIdle: function () {
                              var first_id = message_list.all.first().id;
                              exports.load_old_messages({
                                  anchor: first_id,
                                  num_before: backfill_batch_size,
                                  num_after: 0,
                                  msg_list: home_msg_list,
                              });
                          }});
    }

    if (page_params.have_initial_messages) {
        exports.load_old_messages({
            anchor: page_params.pointer,
            num_before: 200,
            num_after: 200,
            msg_list: home_msg_list,
            cont: load_more,
        });
    } else {
        server_events.home_view_loaded();
    }
});


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = message_fetch;
}
