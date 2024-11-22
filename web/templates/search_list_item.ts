import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import render_input_pill from "./input_pill.ts";

export default function render_search_list_item(context) {
    const out = html`<div class="search_list_item">
        <span>${{__html: context.description_html}}</span>
        ${to_bool(context.is_people)
            ? to_array(context.users).map(
                  (user) => html`
                      <span class="pill-container">
                          ${{__html: render_input_pill(user.user_pill_context)}}
                      </span>
                  `,
              )
            : ""}
    </div> `;
    return to_html(out);
}
