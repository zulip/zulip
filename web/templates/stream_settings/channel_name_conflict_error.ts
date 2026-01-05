import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_channel_name_conflict_error(context) {
    const out = to_bool(context.is_archived)
        ? html`${to_bool(context.can_view_channel)
              ? $html_t(
                    {
                        defaultMessage:
                            "An <z-link>archived channel</z-link> with this name already exists.",
                    },
                    {
                        ["z-link"]: (content) =>
                            html`<a
                                href="#channels/${context.stream_id}/general"
                                class="stream-settings-link"
                                >${content}</a
                            >`,
                    },
                )
              : html`
                    ${$t({defaultMessage: "An archived channel with this name already exists."})}
                `}${to_bool(context.show_rename)
              ? html`
                    <a id="archived_stream_rename" data-stream-id="${context.stream_id}"
                        >${$t({defaultMessage: "Rename it"})}</a
                    >
                `
              : ""}`
        : to_bool(context.can_view_channel)
          ? $html_t(
                {defaultMessage: "A <z-link>channel</z-link> with this name already exists."},
                {
                    ["z-link"]: (content) =>
                        html`<a
                            href="#channels/${context.stream_id}/general"
                            class="stream-settings-link"
                            >${content}</a
                        >`,
                },
            )
          : html` ${$t({defaultMessage: "A channel with this name already exists."})} `;
    return to_html(out);
}
