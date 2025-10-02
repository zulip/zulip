import _ from "lodash";
import assert from "minimalistic-assert";

import * as browser_history from "./browser_history.ts";
import type {Filter} from "./filter.ts";
import * as hash_util from "./hash_util.ts";
import * as message_lists from "./message_lists.ts";
import * as narrow_state from "./narrow_state.ts";

function is_URL_hash_same_as_filter_hash(filter: Filter): boolean {
    if (filter.is_in_home()) {
        if (window.location.hash === "#feed") {
            return true;
        }

        if (window.location.hash === "") {
            return browser_history.get_home_view_hash() === "#feed";
        }
    }

    const hash_from_filter = hash_util.search_terms_to_hash(filter.terms());
    return window.location.hash === hash_from_filter;
}

// Saves the selected message of the narrow in the browser
// history, so that we are able to restore it if the user
// navigates back to this page.
function _save_narrow_state(): void {
    if (message_lists.current === undefined) {
        return;
    }

    const current_filter = narrow_state.filter();
    assert(current_filter !== undefined);
    // Only save state if the URL hash matches the filter terms.
    if (!is_URL_hash_same_as_filter_hash(current_filter)) {
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
    browser_history.update_current_history_state_data(narrow_data);
}

// Safari limits you to 100 replaceState calls in 30 seconds.
export const save_narrow_state = _.throttle(_save_narrow_state, 500);

// This causes the save to happen right away.
export function save_narrow_state_and_flush(): void {
    save_narrow_state();
    save_narrow_state.flush();
}
