const FetchStatus = function () {

    const self = {};

    // The FetchStatus object tracks tracks the state of a
    // message_list_data object, whether rendered in the DOM or not,
    // and is the source of truth for whether the message_list_data
    // object has the complete history of the view or whether more
    // messages should be loaded when scrolling to the top or bottom
    // of the message feed.
    let loading_older = false;
    let loading_newer = false;
    let found_oldest = false;
    let found_newest = false;
    let history_limited = false;

    // Tracks the highest message ID that we know exist in this view,
    // but are not within the contiguous range of messages we have
    // received from the server.  Used to correctly handle a rare race
    // condition where a newly sent message races with fetching a
    // group of messages that would lead to found_newest being set
    // (described in detail below).
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
        // Returns true if and only if the caller needs to trigger an
        // additional fetch due to the race described below.
        const found_max_message_id = max_id_for_messages(messages);
        loading_newer = false;
        found_newest = opts.found_newest;
        if (opts.update_loading_indicator) {
            message_scroll.hide_loading_newer();
        }
        if (found_newest && expected_max_message_id > found_max_message_id) {
            // This expected_max_message_id logic is designed to
            // resolve a subtle race condition involving newly sent
            // messages in a view that does not display the currently
            // latest messages.
            //
            // When a new message arrives matching the current view
            // and found_newest is false, we cannot add the message to
            // the view in-order without creating invalid output
            // (where two messages are displaye adjacent but might be
            // weeks and hundreds of messages apart in actuality).
            //
            // So we have to discard those messages.  Usually, this is
            // fine; the client will receive those when the user
            // scrolls to the bottom of the page, triggering another
            // fetch.  With that solution, a rare race is still possible,
            // with this sequence:
            //
            // 1. Client initiates GET /messages to fetch the last
            //    batch of messages in this view.  The server
            //    completes the database access and and starts sending
            //    the response with found_newest=true.
            // 1. A new message is sent matching the view, the event reaches
            //    the client.  We discard the message because found_newest=false.
            // 1. The client receives the GET /messages response, and
            //    marks found_newest=true.  As a result, it believes is has
            //    the latest messages and won't fetch more, but is missing the
            //    recently sent message.
            //
            // To address this problem, we track the highest message
            // ID among messages that were discarded due to
            // fetch_status in expected_max_message_id.  If that is
            // higher than the highest ID returned in a GET /messages
            // response with found_newest=true, we know the above race
            // has happened and trigger an additional fetch.
            found_newest = false;

            // Resetting our tracked last message id is an important
            // circuit-breaker for cases where the message(s) that we
            // "know" exist were deleted or moved to another topic.
            expected_max_message_id = 0;
            return true;
        }
        return false;
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
