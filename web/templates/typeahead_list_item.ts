import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
import render_inline_decorated_stream_name from "./inline_decorated_stream_name.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_typeahead_list_item(context) {
    const out = html`${to_bool(context.is_emoji)
            ? to_bool(context.has_image)
                ? html` <img class="emoji" src="${context.img_src}" /> `
                : html` <span class="emoji emoji-${context.emoji_code}"></span> `
            : to_bool(context.is_person)
              ? html`${to_bool(context.user_circle_class)
                    ? html` <span class="${context.user_circle_class} user_circle"></span> `
                    : ""}${to_bool(context.has_image)
                    ? html` <img class="typeahead-image" src="${context.img_src}" /> `
                    : html`
                          <i
                              class="typeahead-image zulip-icon zulip-icon-triple-users no-presence-circle"
                          ></i>
                      `}`
              : to_bool(context.is_user_group)
                ? html`
                      <i
                          class="typeahead-image zulip-icon zulip-icon-triple-users no-presence-circle"
                          aria-hidden="true"
                      ></i>
                  `
                : ""}${
            /* Separate container to ensure overflowing text remains in this container. */ ""
        }
        <div
            class="typeahead-text-container${to_bool(context.has_secondary_html)
                ? " has_secondary_html"
                : ""}"
        >
            <strong class="typeahead-strong-section"
                >${to_bool(context.stream)
                    ? {__html: render_inline_decorated_stream_name({stream: context.stream})}
                    : context.primary}</strong
            >${to_bool(context.is_bot)
                ? html`
                      <i
                          class="zulip-icon zulip-icon-bot"
                          aria-label="${$t({defaultMessage: "Bot"})}"
                      ></i>
                  `
                : ""}${to_bool(context.has_pronouns)
                ? html` <span class="pronouns"
                      >${context.pronouns}${to_bool(context.has_secondary_html) ||
                      to_bool(context.has_secondary)
                          ? ","
                          : ""}</span
                  >`
                : ""}${to_bool(context.should_add_guest_user_indicator)
                ? html` <i>(${$t({defaultMessage: "guest"})})</i>`
                : ""}${to_bool(context.has_status)
                ? html` ${{__html: render_status_emoji(context.status_emoji_info)}}`
                : ""}${to_bool(context.has_secondary_html)
                ? html` <span
                      class="autocomplete_secondary rendered_markdown single-line-rendered-markdown"
                      >${{__html: postprocess_content(context.secondary_html)}}</span
                  >`
                : to_bool(context.has_secondary)
                  ? html` <span class="autocomplete_secondary">${context.secondary}</span>`
                  : ""}
        </div> `;
    return to_html(out);
}
