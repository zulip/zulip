import * as message_feed_loading from "./message_feed_loading";
import type {RawMessage} from "./types";

function max_id_for_messages(messages: RawMessage[]): number {
    let max_id = 0;
    for (const msg of messages) {
        max_id = Math.max(max_id, msg.id);
    }
    return max_id;
}

export class FetchStatus {
    // The FetchStatus object tracks the state of a
    // message_list_data object, whether rendered in the DOM or not,
    // and is the source of truth for whether the message_list_data
    // object has the complete history of the view or whether more
    // messages should be loaded when scrolling to the top or bottom
    // of the message feed.
    _loading_older = false;
    _loading_newer = false;
    _found_oldest = false;
    _found_newest = false;
    _history_limited = false;

    // Tracks the highest message ID that we know exist in this view,
    // but are not within the contiguous range of messages we have
    // received from the server.  Used to correctly handle a rare race
    // condition where a newly sent message races with fetching a
    // group of messages that would lead to found_newest being set
    // (described in detail below).
    _expected_max_message_id = 0;

    start_older_batch(opts: {update_loading_indicator: boolean}): void {
        this._loading_older = true;
        if (opts.update_loading_indicator) {
            message_feed_loading.show_loading_older();
        }
    }

    finish_older_batch(opts: {
        found_oldest: boolean;
        history_limited: boolean;
        update_loading_indicator: boolean;
    }): void {
        this._loading_older = false;
        this._found_oldest = opts.found_oldest;
        this._history_limited = opts.history_limited;
        if (opts.update_loading_indicator) {
            message_feed_loading.hide_loading_older();
        }
    }

    can_load_older_messages(): boolean {
        return !this._loading_older && !this._found_oldest;
    }

    has_found_oldest(): boolean {
        return this._found_oldest;
    }

    history_limited(): boolean {
        return this._history_limited;
    }

    start_newer_batch(opts: {update_loading_indicator: boolean}): void {
        this._loading_newer = true;
        if (opts.update_loading_indicator) {
            message_feed_loading.show_loading_newer();
        }
    }

    finish_newer_batch(
        messages: RawMessage[],
        opts: {update_loading_indicator: boolean; found_newest: boolean},
    ): boolean {
        // Returns true if and only if the caller needs to trigger an
        // additional fetch due to the race described below.
        const found_max_message_id = max_id_for_messages(messages);
        this._loading_newer = false;
        this._found_newest = opts.found_newest;
        if (opts.update_loading_indicator) {
            message_feed_loading.hide_loading_newer();
        }
        if (this._found_newest && this._expected_max_message_id > found_max_message_id) {
            // This expected_max_message_id logic is designed to
            // resolve a subtle race condition involving newly sent
            // messages in a view that does not display the currently
            // latest messages.
            //
            // When a new message arrives matching the current view
            // and found_newest is false, we cannot add the message to
            // the view in-order without creating invalid output
            // (where two messages are display adjacent but might be
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
            this._found_newest = false;

            // Resetting our tracked last message id is an important
            // circuit-breaker for cases where the message(s) that we
            // "know" exist were deleted or moved to another topic.
            this._expected_max_message_id = 0;
            return true;
        }
        return false;
    }

    can_load_newer_messages(): boolean {
        return !this._loading_newer && !this._found_newest;
    }

    has_found_newest(): boolean {
        return this._found_newest;
    }

    update_expected_max_message_id(messages: RawMessage[]): void {
        this._expected_max_message_id = Math.max(
            this._expected_max_message_id,
            max_id_for_messages(messages),
        );
    }
}
