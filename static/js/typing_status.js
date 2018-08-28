var typing_status = (function () {

var exports = {};

// See docs/subsystems/typing-indicators.md for details on typing indicators.

// The following constants are tuned to work with
// TYPING_STARTED_EXPIRY_PERIOD, which is what the other
// users will use to time out our messages.  (Or us,
// depending on your perspective.) See typing_events.js.

// How frequently 'still typing' notifications are sent
// to extend the expiry
var TYPING_STARTED_WAIT_PERIOD = 10000; // 10s
// How long after someone stops editing in the compose box
// do we send a 'stopped typing' notification
var TYPING_STOPPED_WAIT_PERIOD = 5000; // 5s

/*

    Our parent should pass in a worker object with the following
    callbacks:

        notify_server_start
        notify_server_stop
        get_recipient
        get_current_time
        is_valid_conversation

    See typing.js for the implementations of the above. (Our
    node tests also act as workers and will stub those functions
    appropriately.)
*/

exports.state = {};

exports.initialize_state = function () {
    exports.state.current_recipient =  undefined;
    exports.state.next_send_start_time =  undefined;
    exports.state.idle_timer = undefined;
};

exports.initialize_state();

function stop_last_notification(worker) {
    var state = exports.state;
    if (state.idle_timer) {
        clearTimeout(state.idle_timer);
    }
    worker.notify_server_stop(state.current_recipient);
    exports.initialize_state();
}

function start_or_extend_idle_timer(worker) {
    var state = exports.state;
    function on_idle_timeout() {
        // We don't do any real error checking here, because
        // if we've been idle, we need to tell folks, and if
        // our current recipient has changed, previous code will
        // have stopped the timer.
        stop_last_notification(worker);
    }

    if (state.idle_timer) {
        clearTimeout(state.idle_timer);
    }
    state.idle_timer = setTimeout(
        on_idle_timeout,
        TYPING_STOPPED_WAIT_PERIOD
    );
}

function set_next_start_time(current_time) {
    exports.state.next_send_start_time = current_time + TYPING_STARTED_WAIT_PERIOD;
}

function actually_ping_server(worker, recipient, current_time) {
    worker.notify_server_start(recipient);
    set_next_start_time(current_time);
}

function maybe_ping_server(worker, recipient) {
    var current_time = worker.get_current_time();
    if (current_time > exports.state.next_send_start_time) {
        actually_ping_server(worker, recipient, current_time);
    }
}

exports.handle_text_input = function (worker) {
    var new_recipient = worker.get_recipient();
    var current_recipient = exports.state.current_recipient;

    if (current_recipient) {
        if (new_recipient === current_recipient) {
            // Nothing has really changed, except we may need
            // to send a ping to the server.
            maybe_ping_server(worker, new_recipient);

            // We can also extend out our idle time.
            start_or_extend_idle_timer(worker);

            return;
        }

        // We apparently stopped talking to our old recipient,
        // so we must stop the old notification.  Don't return
        // yet, because we may have a new recipient.
        stop_last_notification(worker);

    }

    if (!worker.is_valid_conversation(new_recipient)) {
        // If we are not talking to somebody we care about,
        // then there is no more action to take.
        return;
    }

    // We just started talking to this recipient, so notify
    // the server.
    exports.state.current_recipient = new_recipient;
    var current_time = worker.get_current_time();
    actually_ping_server(worker, new_recipient, current_time);
    start_or_extend_idle_timer(worker);
};

exports.stop = function (worker) {
    // We get this if somebody closes the compose box, but
    // it doesn't necessarily mean we had typing indicators
    // active before this.
    if (exports.state.current_recipient) {
        stop_last_notification(worker);
    }
};


return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = typing_status;
}
window.typing_status = typing_status;
