import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_preferences_emoji from "./preferences_emoji.ts";
import render_preferences_general from "./preferences_general.ts";
import render_preferences_information from "./preferences_information.ts";
import render_preferences_left_sidebar from "./preferences_left_sidebar.ts";
import render_preferences_navigation from "./preferences_navigation.ts";
import render_privacy_settings from "./privacy_settings.ts";

export default function render_preferences(context) {
    const out = html`<form class="preferences-settings-form">
        ${{__html: render_preferences_general(context)}}${
            /* user_has_email_set is passed as true here, because we don't disable the dropdown in organization panel also there's no need to show tooltip here. */ ""
        }
        ${to_bool(context.for_realm_settings)
            ? {
                  __html: render_privacy_settings({
                      user_has_email_set: true,
                      hide_read_receipts_tooltip: true,
                      read_receipts_help_icon_tooltip_text: "",
                      prefix: "realm_",
                      ...context,
                  }),
              }
            : ""}
        ${{__html: render_preferences_emoji(context)}}
        ${{__html: render_preferences_navigation(context)}}
        ${{__html: render_preferences_information(context)}}
        ${{__html: render_preferences_left_sidebar(context)}}
    </form> `;
    return to_html(out);
}
