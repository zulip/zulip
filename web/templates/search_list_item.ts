import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import render_input_pill from "./input_pill.ts";
import render_search_user_pill from "./search_user_pill.ts";

export default function render_search_list_item(context) {
    const out = html`<div class="search_list_item">
        ${to_array(context.pills).map((pill) =>
            pill.operator === "search"
                ? html` <div class="description">${{__html: pill.description_html}}</div> `
                : pill.type === "search_user"
                  ? html`
                        <span class="pill-container"
                            >${{__html: render_search_user_pill(pill)}}</span
                        >
                    `
                  : html`
                        <span class="pill-container">${{__html: render_input_pill(pill)}}</span>
                    `,
        )}
        ${to_bool(context.description_html)
            ? html`<div class="description">${{__html: context.description_html}}</div>`
            : ""}
    </div> `;
    return to_html(out);
}
