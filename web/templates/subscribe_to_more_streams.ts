import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_subscribe_to_more_streams(context) {
    const out = to_bool(context.exactly_one_unsubscribed_stream)
        ? html`
              <a class="subscribe-more-link" href="#channels/available">
                  <i
                      class="subscribe-more-icon zulip-icon zulip-icon-browse-channels"
                      aria-hidden="true"
                  ></i>
                  <span class="subscribe-more-label"
                      >${$t({defaultMessage: "BROWSE 1 MORE CHANNEL"})}</span
                  >
              </a>
          `
        : to_bool(context.can_subscribe_stream_count)
          ? html`
                <a class="subscribe-more-link" href="#channels/available">
                    <i
                        class="subscribe-more-icon zulip-icon zulip-icon-browse-channels"
                        aria-hidden="true"
                    ></i>
                    <span class="subscribe-more-label"
                        >${$t(
                            {defaultMessage: "BROWSE {can_subscribe_stream_count} MORE CHANNELS"},
                            {can_subscribe_stream_count: context.can_subscribe_stream_count},
                        )}</span
                    >
                </a>
            `
          : to_bool(context.can_create_streams)
            ? html`
                  <a class="subscribe-more-link" href="#channels/new">
                      <i
                          class="subscribe-more-icon zulip-icon zulip-icon-browse-channels"
                          aria-hidden="true"
                      ></i>
                      <span class="subscribe-more-label"
                          >${$t({defaultMessage: "CREATE A CHANNEL"})}</span
                      >
                  </a>
              `
            : "";
    return to_html(out);
}
