import * as channel from "./channel";
import * as message_view from "./message_view";
import {page_params} from "./page_params";
import * as people from "./people";

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
        message_view.show(
            [
                {
                    operator: "dm",
                    operand: people.WELCOME_BOT.user_id,
                },
            ],
            {trigger: "sidebar"},
        );
    }
}
