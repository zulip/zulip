import _ from "lodash";
import assert from "minimalistic-assert";

import * as browser_history from "./browser_history";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";

// Saves the selected message of the narrow in the browser
// history, so that we are able to restore it if the user
// navigates back to this page.
function _save_narrow_state(): void {
    const current_filter = narrow_state.filter();
    if (current_filter === undefined) {
        return;
    }

    assert(message_lists.current !== undefined);
    // We don't want to save state in the middle of a narrow change
    // to the wrong hash.
    if (browser_history.state.changing_hash) {
        return;
    }

    const narrow_pointer = message_lists.current.selected_id();
    if (narrow_pointer === -1) {
        return;
    }
    const $narrow_row = message_lists.current.selected_row();
    if ($narrow_row.length === 0) {
        return;
    }
    const narrow_offset = $narrow_row.get_offset_to_window().top;
    const narrow_data = {
        narrow_pointer,
        narrow_offset,
    };
    history.replaceState(narrow_data, "", window.location.href);
}

// Safari limits you to 100 replaceState calls in 30 seconds.
export const save_narrow_state = _.throttle(_save_narrow_state, 500);

// This causes the save to happen right away.
export function save_narrow_state_and_flush(): void {
    save_narrow_state();
    save_narrow_state.flush();
}
