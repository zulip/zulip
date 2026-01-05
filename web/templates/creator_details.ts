import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";
import render_user_display_only_pill from "./user_display_only_pill.ts";

export default function render_creator_details(context) {
    const out = html`${to_bool(context.creator)
        ? $html_t(
              {
                  defaultMessage:
                      "Created by <z-user></z-user> on <z-date-created></z-date-created>.",
              },
              {
                  ["z-user"]: () =>
                      html` ${{
                          __html: render_user_display_only_pill({
                              is_active: context.creator.is_active,
                              is_current_user: context.is_creator,
                              display_value: context.creator.full_name,
                              img_src: context.creator.avatar_url,
                              user_id: context.creator.user_id,
                              is_inline: true,
                          }),
                      }}`,
                  ["z-date-created"]: () => context.date_created_string,
              },
          )
        : $html_t(
              {defaultMessage: "Created on <z-date-created></z-date-created>."},
              {["z-date-created"]: () => context.date_created_string},
          )}${to_bool(context.stream_id)
        ? $html_t(
              {defaultMessage: "&nbsp;Channel ID: {stream_id}."},
              {stream_id: context.stream_id},
          )
        : ""}${to_bool(context.group_id)
        ? $html_t({defaultMessage: "&nbsp;Group ID: {group_id}."}, {group_id: context.group_id})
        : ""}`;
    return to_html(out);
}
