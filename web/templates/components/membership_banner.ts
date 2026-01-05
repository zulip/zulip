import {html, to_html} from "../../src/html.ts";
import render_user_group_membership_request_result from "../user_group_settings/user_group_membership_request_result.ts";
import render_banner from "./banner.ts";

export default function render_membership_banner(context) {
    const out = html`${{
        __html: render_banner(
            context,
            (context1) => html` ${{__html: render_user_group_membership_request_result(context1)}}`,
        ),
    }} `;
    return to_html(out);
}
