import {to_array} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_inbox_folder_row from "./inbox_folder_row.ts";
import render_inbox_row from "./inbox_row.ts";

export default function render_inbox_folder_with_channels(context) {
    const out = html`${{
            __html: render_inbox_folder_row({
                unread_count: context.unread_count,
                has_unread_mention: context.has_unread_mention,
                is_collapsed: context.is_collapsed,
                is_dm_header: false,
                is_header_visible: context.is_header_visible,
                header_id: context.header_id,
                name: context.name,
            }),
        }}
        <div class="inbox-streams-container inbox-folder-components">
            ${to_array(context.topics_dict).map((topics_entry) =>
                to_array(context.streams_dict).map((stream_entry) =>
                    stream_entry[1].folder_id === context.id && stream_entry[0] === topics_entry[0]
                        ? html`
                              <div id="${topics_entry[0]}" class="inbox-folder-channel">
                                  ${{__html: render_inbox_row(stream_entry[1])}}
                                  <div class="inbox-topic-container">
                                      ${to_array(topics_entry[1]).map(
                                          (context3) =>
                                              html` ${{__html: render_inbox_row(context3[1])}}`,
                                      )}
                                  </div>
                              </div>
                          `
                        : "",
                ),
            )}
        </div> `;
    return to_html(out);
}
