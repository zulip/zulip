import _ from "lodash";

import * as hash_util from "./hash_util";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";

// Saves the selected message of the narrow in the browser
// history, so that we are able to restore it if the user
// navigates back to this page.
function _save_narrow_state() {
    if (!narrow_state.active()) {
        return;
    }

    // We don't want to save state in the middle of a narrow change
    // to the wrong hash.
    const current_filter = message_lists.current.data.filter;
    if (hash_util.operators_to_hash(current_filter.operators()) !== window.location.hash) {
        return;
    }

    const narrow_data = {};
    const narrow_pointer = message_lists.current.selected_id();
    if (narrow_pointer === -1) {
        return;
    }
    narrow_data.narrow_pointer = narrow_pointer;
    const $narrow_row = message_lists.current.selected_row();
    if ($narrow_row.length === 0) {
        return;
    }
    narrow_data.narrow_offset = $narrow_row.get_offset_to_window().top;
    history.replaceState(narrow_data, "", window.location.href);
}

// Safari limits you to 100 replaceState calls in 30 seconds.
export const save_narrow_state = _.throttle(_save_narrow_state, 500);

// This causes the save to happen right away.
export function save_narrow_state_and_flush() {
    save_narrow_state();
    save_narrow_state.flush();
}
