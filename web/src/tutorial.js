import * as channel from "./channel";
import * as message_view from "./message_view";
import {page_params} from "./page_params";

const set_tutorial_status = (status, callback) =>
    channel.post({
        url: "/json/users/me/tutorial_status",
        data: {status},
        success: callback,
    });

export const initialize = () => {
    if (page_params.needs_tutorial) {
        set_tutorial_status("started");
        message_view.show(
            [
                {
                    operator: "is",
                    operand: "private",
                },
            ],
            {trigger: "sidebar"},
        );
    }
};
