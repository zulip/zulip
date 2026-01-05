import {html, to_html} from "../../src/html.ts";
import render_stream_subscription_request_result from "../stream_settings/stream_subscription_request_result.ts";
import render_banner from "./banner.ts";

export default function render_subscription_banner(context) {
    const out = html`${{
        __html: render_banner(
            context,
            (context1) => html` ${{__html: render_stream_subscription_request_result(context1)}}`,
        ),
    }} `;
    return to_html(out);
}
