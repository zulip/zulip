import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_inline_decorated_stream_name from "../inline_decorated_stream_name.ts";

export default function render_first_stream_created_modal(context) {
    const out = html`${$t({
            defaultMessage:
                "You will now see the channel you created. To go back to channel settings, you can:",
        })}
        <ul>
            <li>
                ${$html_t(
                    {
                        defaultMessage:
                            "Click on <z-stream></z-stream> at the top of your Zulip window.",
                    },
                    {
                        ["z-stream"]: () =>
                            html`<b
                                >${{
                                    __html: render_inline_decorated_stream_name({
                                        stream: context.stream,
                                    }),
                                }}</b
                            >`,
                    },
                )}
            </li>
            <li>
                ${$html_t({
                    defaultMessage: "Use the <b>back</b> button in your browser or desktop app.",
                })}
            </li>
        </ul> `;
    return to_html(out);
}
