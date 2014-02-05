var reload = (function () {

var exports = {};

var reload_in_progress = false;
var reload_pending = false;

exports.is_pending = function () {
    return reload_pending;
};

exports.is_in_progress = function () {
    return reload_in_progress;
};

function preserve_state(send_after_reload) {
    if (send_after_reload === undefined) {
        send_after_reload = 0;
    }
    var url = "#reload:send_after_reload=" + Number(send_after_reload);
    url += "+csrf_token=" + encodeURIComponent(csrf_token);

    if (compose.composing() === 'stream') {
        url += "+msg_type=stream";
        url += "+stream=" + encodeURIComponent(compose.stream_name());
        url += "+subject=" + encodeURIComponent(compose.subject());
    } else if (compose.composing() === 'private') {
        url += "+msg_type=private";
        url += "+recipient=" + encodeURIComponent(compose.recipient());
    }

    if (compose.composing()){
        url += "+msg=" + encodeURIComponent(compose.message_content());
    }

    var pointer = current_msg_list.selected_id();
    if (pointer !== -1) {
        url += "+pointer=" + pointer;
    }
    var row = current_msg_list.selected_row();
    if (row.length > 0) {
        url += "+offset=" + row.offset().top;
    }

    var oldhash = window.location.hash;
    if (oldhash.length !== 0 && oldhash[0] === '#') {
        oldhash = oldhash.slice(1);
    }
    url += "+oldhash=" + encodeURIComponent(oldhash);

    window.location.replace(url);
}

// Check if we're doing a compose-preserving reload.  This must be
// done before the first call to get_events
$(function () {
    var location = window.location.toString();
    var fragment = location.substring(location.indexOf('#') + 1);
    if (fragment.search("reload:") !== 0) {
        return;
    }
    fragment = fragment.replace(/^reload:/, "");
    var keyvals = fragment.split("+");
    var vars = {};
    _.each(keyvals, function (str) {
        var pair = str.split("=");
        vars[pair[0]] = decodeURIComponent(pair[1]);
    });

    // Prevent random people on the Internet from constructing links
    // that make you send a message.
    if (vars.csrf_token !== csrf_token) {
        return;
    }

    if (vars.msg !== undefined){
        var send_now = parseInt(vars.send_after_reload, 10);

        // TODO: preserve focus
        compose.start(vars.msg_type, {stream: vars.stream || '',
                                      subject: vars.subject || '',
                                      private_message_recipient: vars.recipient || '',
                                      content: vars.msg || ''});
        if (send_now) {
            compose.finish();
        }
    }

    var pointer = parseInt(vars.pointer, 10);

    if (pointer) {
        page_params.orig_initial_pointer = page_params.initial_pointer;
        page_params.initial_pointer = pointer;
    }
    var offset = parseInt(vars.offset, 10);
    if (offset) {
        page_params.initial_offset = offset;
    }

    activity.new_user_input = false;
    hashchange.changehash(vars.oldhash);
});

function clear_message_list(msg_list) {
    if (!msg_list) { return; }
    msg_list.clear();
    // Some pending ajax calls may still be processed and they to not expect an
    // empty msg_list.
    msg_list._items = [{id: 1}];
}

function do_reload_app(send_after_reload, save_state, message) {
    // TODO: we should completely disable the UI here
    if (save_state) {
        preserve_state(send_after_reload);
    }

    if (message === undefined) {
        message = "Reloading";
    }
    // TODO: We need a better API for showing messages.
    ui.report_message(message, $("#reloading-application"));
    blueslip.log('Starting server requested page reload');
    reload_in_progress = true;
    try {
        // Unbind all the jQuery event listeners
        $('*').off();

        // Free all of the DOM
        $("html").empty();

        // Now that the DOM is empty our beforeunload callback has been
        // removed.
        server_events.cleanup_event_queue();

        // Empty the large collections
        clear_message_list(all_msg_list);
        clear_message_list(home_msg_list);
        clear_message_list(narrowed_msg_list);
        message_store.clear();

    } catch (ex) {
        blueslip.error('Failed to cleanup before reloading',
                       undefined, ex.stack);
    }
    window.location.reload(true);
}

exports.initiate = function (options) {
    options = _.defaults({}, options, {
        immediate: false,
        save_state: true,
        send_after_reload: false
    });

    if (options.immediate) {
        do_reload_app(options.send_after_reload, options.save_state, options.message);
    }

    if (reload_pending) {
        return;
    }
    reload_pending = true;

    // If the user is composing a message, reload if they become idle
    // while composing.  If they finish or cancel the compose, wait
    // until they're idle again
    var idle_control;
    var unconditional_timeout = 1000*60*30 + util.random_int(0, 1000*60*5);
    var composing_timeout     = 1000*60*5  + util.random_int(0, 1000*60);
    var home_timeout          = 1000*60    + util.random_int(0, 1000*60);
    var compose_done_handler, compose_started_handler;

    function reload_from_idle () {
        do_reload_app(false, options.save_state, options.message);
    }

    // Make sure we always do a reload eventually
    setTimeout(reload_from_idle, unconditional_timeout);

    compose_done_handler = function () {
        idle_control.cancel();
        idle_control = $(document).idle({'idle': home_timeout,
                                         'onIdle': reload_from_idle});
        $(document).off('compose_canceled.zulip compose_finished.zulip',
                        compose_done_handler);
        $(document).on('compose_started.zulip', compose_started_handler);
    };
    compose_started_handler = function () {
        idle_control.cancel();
        idle_control = $(document).idle({'idle': composing_timeout,
                                         'onIdle': reload_from_idle});
        $(document).off('compose_started.zulip', compose_started_handler);
        $(document).on('compose_canceled.zulip compose_finished.zulip',
                       compose_done_handler);
    };

    if (compose.composing()) {
        idle_control = $(document).idle({'idle': composing_timeout,
                                         'onIdle': reload_from_idle});
        $(document).on('compose_canceled.zulip compose_finished.zulip',
                       compose_done_handler);
    } else {
        idle_control = $(document).idle({'idle': home_timeout,
                                         'onIdle': reload_from_idle});
        $(document).on('compose_started.zulip', compose_started_handler);
    }
};

return exports;
}());
