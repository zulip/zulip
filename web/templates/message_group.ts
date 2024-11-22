import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import render_bookend from "./bookend.ts";
import render_recipient_row from "./recipient_row.ts";
import render_single_message from "./single_message.ts";

export default function render_message_group(context) {
    const out = /* Client-side Handlebars template for rendering messages. */ html` ${to_array(
        context.message_groups,
    ).map(
        (message_group) =>
            html`${to_bool(message_group.bookend_top)
                    ? html` ${{__html: render_bookend(message_group)}}`
                    : ""}
                <div class="recipient_row" id="${message_group.message_group_id}">
                    ${{
                        __html: render_recipient_row({
                            use_match_properties: context.use_match_properties,
                            ...message_group,
                        }),
                    }}${to_array(message_group.message_containers).map(
                        (message_container) =>
                            html` ${{
                                __html: render_single_message({
                                    is_archived: message_group.is_archived,
                                    message_list_id: context.message_list_id,
                                    use_match_properties: context.use_match_properties,
                                    ...message_container,
                                }),
                            }}`,
                    )}
                </div> `,
    )}`;
    return to_html(out);
}
