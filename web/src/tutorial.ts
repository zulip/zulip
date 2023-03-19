import * as channel from "./channel";
import * as narrow from "./narrow";

function set_tutorial_status(status: string, callback?: JQuery.jqXHR.DoneCallback | null): JQuery.jqXHR {
    return channel.post({
        url: "/json/users/me/tutorial_status",
        data: {status},
        success: callback,
    });
}

export function initialize(needs_tutorial: boolean | null) : void {
    if (needs_tutorial) {
        set_tutorial_status("started");
        narrow.by("is", "private", {trigger: "sidebar"});
    }
}
