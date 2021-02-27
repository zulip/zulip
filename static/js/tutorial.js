import * as channel from "./channel";

function set_tutorial_status(status, callback) {
    return channel.post({
        url: "/json/users/me/tutorial_status",
        data: {status: JSON.stringify(status)},
        success: callback,
    });
}

export function initialize() {
    if (page_params.needs_tutorial) {
        set_tutorial_status("started");
        narrow.by("is", "private", {trigger: "sidebar"});
    }
}
