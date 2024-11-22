import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import {postprocess_content} from "../../src/postprocess_content.ts";

export default function render_stream_description(context) {
    const out = to_bool(context.rendered_description)
        ? html`<span class="sub-stream-description rendered_markdown">
              ${{__html: postprocess_content(context.rendered_description)}}
          </span> `
        : html`<span class="sub-stream-description no-description">
              ${$t({defaultMessage: "This channel does not yet have a description."})}
          </span> `;
    return to_html(out);
}
