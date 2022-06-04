import * as channel from "./channel";
import * as hashchange from "./hashchange";
import * as narrow from "./narrow";
import {page_params} from "./page_params";

function set_tutorial_status(status, callback) {
    return channel.post({
        url: "/json/users/me/tutorial_status",
        data: {status},
        success: callback,
    });
}

export function initialize() {
    if (page_params.needs_tutorial) {
        set_tutorial_status("started");
        // If a spectator clicked signup from a narrow other than the default view,
        // then, we don't show welcome bot message first to the user.
        if (hashchange.is_current_hash_default_view()) {
            narrow.by("is", "private", {trigger: "sidebar"});
        }
    }
}
