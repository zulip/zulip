import render_user_full_name from "../templates/user_full_name.hbs";

import * as h from "./html.ts";
import * as pure_dom from "./pure_dom.ts";

export function partial_demo_with_user_full_name(info: {
    should_add_guest_user: boolean;
    name: string;
    is_hidden: boolean;
    is_current_user: boolean;
}): h.Block {
    function h5_wrapper(): h.Tag {
        return h.h5_tag({
            children: [
                h.partial({
                    inner_label: "user_full_name",
                    trusted_html: h.trusted_html(render_user_full_name(info)),
                }),
            ],
            pink: true,
        });
    }
    return h.block({elements: [h5_wrapper()]});
}
document.querySelector("#app")!.innerHTML = pure_dom.poll_widget().as_raw_html();
