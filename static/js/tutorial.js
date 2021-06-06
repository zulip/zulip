import * as channel from "./channel";
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
        narrow.by("is", "private", {trigger: "sidebar"});
    }
}
