import {to_array} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_inbox_folder_row from "./inbox_folder_row.ts";
import render_inbox_folder_with_channels from "./inbox_folder_with_channels.ts";
import render_inbox_row from "./inbox_row.ts";

export default function render_inbox_list(context) {
    const out = html`${{
            __html: render_inbox_folder_row({
                unread_count: context.unread_dms_count,
                has_unread_mention: context.has_unread_mention,
                is_collapsed: context.is_dms_collapsed,
                is_dm_header: true,
                is_header_visible: context.has_dms_post_filter,
                header_id: "inbox-dm-header",
            }),
        }}
        <div id="inbox-direct-messages-container" class="inbox-folder-components">
            ${to_array(context.dms_dict).map((dm) => html` ${{__html: render_inbox_row(dm[1])}}`)}
        </div>
        ${to_array(context.channel_folders_dict).map(
            (channel_folder_entry) =>
                html` ${{
                    __html: render_inbox_folder_with_channels({
                        streams_dict: context.streams_dict,
                        topics_dict: context.topics_dict,
                        unread_count: channel_folder_entry[1].unread_count,
                        has_unread_mention: channel_folder_entry[1].has_unread_mention,
                        is_collapsed: channel_folder_entry[1].is_collapsed,
                        is_header_visible: channel_folder_entry[1].is_header_visible,
                        header_id: channel_folder_entry[1].header_id,
                        name: channel_folder_entry[1].name,
                        id: channel_folder_entry[1].id,
                    }),
                }}`,
        )}`;
    return to_html(out);
}
