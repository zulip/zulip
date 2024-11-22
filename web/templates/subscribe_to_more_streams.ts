import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_subscribe_to_more_streams(context) {
    const out = to_bool(context.exactly_one_unsubscribed_stream)
        ? html`
              <a class="subscribe-more-link" href="#channels/notsubscribed">
                  <i
                      class="subscribe-more-icon zulip-icon zulip-icon-square-plus"
                      aria-hidden="true"
                  ></i
                  >${$t({defaultMessage: "BROWSE 1 MORE CHANNEL"})}</a
              >
          `
        : to_bool(context.can_subscribe_stream_count)
          ? html`
                <a class="subscribe-more-link" href="#channels/notsubscribed">
                    <i
                        class="subscribe-more-icon zulip-icon zulip-icon-square-plus"
                        aria-hidden="true"
                    ></i
                    >${$t(
                        {defaultMessage: "BROWSE {can_subscribe_stream_count} MORE CHANNELS"},
                        {can_subscribe_stream_count: context.can_subscribe_stream_count},
                    )}</a
                >
            `
          : to_bool(context.can_create_streams)
            ? html`
                  <a class="subscribe-more-link" href="#channels/new">
                      <i
                          class="subscribe-more-icon zulip-icon zulip-icon-square-plus"
                          aria-hidden="true"
                      ></i
                      >${$t({defaultMessage: "CREATE A CHANNEL"})}</a
                  >
              `
            : "";
    return to_html(out);
}
