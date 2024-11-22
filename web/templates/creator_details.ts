import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t} from "../src/i18n.ts";
import render_user_display_only_pill from "./user_display_only_pill.ts";

export default function render_creator_details(context) {
    const out = to_bool(context.creator)
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
          );
    return to_html(out);
}
