import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_inline_decorated_stream_name from "../inline_decorated_stream_name.ts";

export default function render_announce_stream_checkbox(context) {
    const out = html`<label class="checkbox" for="id_should_announce_new_stream">
        <input
            type="checkbox"
            name="announce"
            value="announce"
            checked
            id="id_should_announce_new_stream"
        />
        <span class="rendered-checkbox"></span>
        ${$t({defaultMessage: "Announce new channel in"})}
        ${to_bool(context.new_stream_announcements_stream_sub)
            ? html`
                  <strong>
                      ${{
                          __html: render_inline_decorated_stream_name({
                              stream: context.new_stream_announcements_stream_sub,
                          }),
                      }}
                  </strong>
              `
            : ""}
        ${{
            __html: render_help_link_widget({
                link: "/help/configure-automated-notices#new-channel-announcements",
            }),
        }}</label
    > `;
    return to_html(out);
}
