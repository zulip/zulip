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

function preserve_compose(send_after_reload) {
    if (send_after_reload === undefined) {
        send_after_reload = 0;
    }
    var url = "#reload:send_after_reload=" + Number(send_after_reload);
    url += "+csrf_token=" + encodeURIComponent(csrf_token);
    if (compose.composing() === 'stream') {
        url += "+msg_type=stream";
        url += "+stream=" + encodeURIComponent(compose.stream_name());
        url += "+subject=" + encodeURIComponent(compose.subject());
    } else {
        url += "+msg_type=private";
        url += "+recipient=" + encodeURIComponent(compose.recipient());
    }
    url += "+msg=" + encodeURIComponent(compose.message_content());

    var oldhash = window.location.hash;
    if (oldhash.length !== 0 && oldhash[0] === '#') {
        oldhash = oldhash.slice(1);
    }
    url += "+oldhash=" + encodeURIComponent(oldhash);

    window.location.replace(url);
}

// Check if we're doing a compose-preserving reload.  This must be
// done before the first call to get_updates
$(function () {
    var location = window.location.toString();
    var fragment = location.substring(location.indexOf('#') + 1);
    if (fragment.search("reload:") !== 0) {
        return;
    }
    fragment = fragment.replace(/^reload:/, "");
    var keyvals = fragment.split("+");
    var vars = {};
    $.each(keyvals, function (idx, str) {
        var pair = str.split("=");
        vars[pair[0]] = decodeURIComponent(pair[1]);
    });

    // Prevent random people on the Internet from constructing links
    // that make you send a message.
    if (vars.csrf_token !== csrf_token) {
        return;
    }

    var send_now = parseInt(vars.send_after_reload, 10);

    hashchange.changehash(vars.oldhash);

    // TODO: preserve focus
    compose.start(vars.msg_type, {stream: vars.stream,
                                  subject: vars.subject,
                                  private_message_recipient: vars.recipient,
                                  content: vars.msg});
    if (send_now) {
        compose.finish();
    }
});

function do_reload_app(send_after_reload, message) {
    // TODO: we should completely disable the UI here
    if (compose.composing()) {
        preserve_compose(send_after_reload);
    }
    if (message === undefined) {
        message = "Reloading";
    }
    // TODO: We need a better API for showing messages.
    ui.report_message(message, $("#reloading-application"));
    reload_in_progress = true;
    window.location.reload(true);
}

exports.initiate = function (options) {
    var defaults = {immediate: false,
                    send_after_reload: false};
    options = $.extend(defaults, options);

    if (options.immediate) {
        do_reload_app(options.send_after_reload, options.message);
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

    // Make sure we always do a reload eventually
    setTimeout(function () { do_reload_app(false, options.message); }, unconditional_timeout);

    function reload_from_idle () {
        do_reload_app(false, options.message);
    }

    compose_done_handler = function () {
        idle_control.cancel();
        idle_control = $(document).idle({'idle': home_timeout,
                                         'onIdle': reload_from_idle});
        $(document).off('compose_canceled.zephyr compose_finished.zephyr',
                        compose_done_handler);
        $(document).on('compose_started.zephyr', compose_started_handler);
    };
    compose_started_handler = function () {
        idle_control.cancel();
        idle_control = $(document).idle({'idle': composing_timeout,
                                         'onIdle': reload_from_idle});
        $(document).off('compose_started.zephyr', compose_started_handler);
        $(document).on('compose_canceled.zephyr compose_finished.zephyr',
                       compose_done_handler);
    };

    if (compose.composing()) {
        idle_control = $(document).idle({'idle': composing_timeout,
                                         'onIdle': reload_from_idle});
        $(document).on('compose_canceled.zephyr compose_finished.zephyr',
                       compose_done_handler);
    } else {
        idle_control = $(document).idle({'idle': home_timeout,
                                         'onIdle': reload_from_idle});
        $(document).on('compose_started.zephyr', compose_started_handler);
    }
};

return exports;
}());
