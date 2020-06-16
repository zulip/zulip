const FetchStatus = function () {

    const self = {};

    let loading_older = false;
    let loading_newer = false;
    let found_oldest = false;
    let found_newest = false;
    let history_limited = false;
    let expected_max_message_id = 0;

    function max_id_for_messages(messages) {
        let max_id = 0;
        for (const msg of messages) {
            max_id = Math.max(max_id, msg.id);
        }
        return max_id;
    }

    self.start_older_batch = function (opts) {
        loading_older = true;
        if (opts.update_loading_indicator) {
            message_scroll.show_loading_older();
        }
    };

    self.finish_older_batch = function (opts) {
        loading_older = false;
        found_oldest = opts.found_oldest;
        history_limited = opts.history_limited;
        if (opts.update_loading_indicator) {
            message_scroll.hide_loading_older();
        }
    };

    self.can_load_older_messages = function () {
        return !loading_older && !found_oldest;
    };

    self.has_found_oldest = function () {
        return found_oldest;
    };

    self.history_limited = function () {
        return history_limited;
    };

    self.start_newer_batch = function (opts) {
        loading_newer = true;
        if (opts.update_loading_indicator) {
            message_scroll.show_loading_newer();
        }
    };

    self.finish_newer_batch = function (messages, opts) {
        const found_max_message_id = max_id_for_messages(messages);
        loading_newer = false;
        found_newest = opts.found_newest;
        if (opts.update_loading_indicator) {
            message_scroll.hide_loading_newer();
        }
        if (found_newest && expected_max_message_id > found_max_message_id) {
            // We may not have inserted the newly received messages into their
            // respective message_list's but we keep track of the last message
            // that should have been added.
            // These messages are loaded into their respective message_lists,
            // through a fetch instead.
            //
            // However there maybe a situation where we discard the newly received
            // messages just after the server responds with the last batch of
            // messages, that has not been updated with these new messages.
            // Thus we refuse to acknowledge the server received `found_newest`
            // and explicitly fetch the newer messages.
            //
            //
            // Note: We reset our tracked last message id to act as a circuit-breaker.
            // And if the race condition mentioned above occurs while we're handling
            // this race condition, `expected_max_message_id` gets updated again.
            // Thus it can again enter this block as the reset value is updated again.
            found_newest = false;
            expected_max_message_id = 0;
            return true;
        }
    };

    self.can_load_newer_messages = function () {
        return !loading_newer && !found_newest;
    };

    self.has_found_newest = function () {
        return found_newest;
    };

    self.update_expected_max_message_id = function (messages) {
        expected_max_message_id = Math.max(expected_max_message_id,
                                           max_id_for_messages(messages));
    };

    return self;

};
module.exports = FetchStatus;
window.FetchStatus = FetchStatus;
