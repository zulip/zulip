import $ from "jquery";
import assert from "minimalistic-assert";

import type {StreamSubscription} from "./sub_store";

export function get_edit_container(sub: StreamSubscription): JQuery {
    assert(sub !== undefined, "Stream subscription is undefined.");
    return $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
            sub.stream_id.toString(),
        )}']`,
    );
}
