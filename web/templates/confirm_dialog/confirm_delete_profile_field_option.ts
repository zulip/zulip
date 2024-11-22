import {html, to_html} from "../../shared/src/html.ts";
import {to_array} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_confirm_delete_profile_field_option(context) {
    const out = html`<p>
${context.count === 1 ? $html_t({defaultMessage: "This will clear the <z-field-name></z-field-name> profile field for 1 user."}, {["z-field-name"]: () => html`<strong>${context.field_name}</strong>`}) : $html_t({defaultMessage: "This will clear the <z-field-name></z-field-name> profile field for <z-count></z-count> users."}, {["z-field-name"]: () => html`<strong>${context.field_name}</strong>`, ["z-count"]: () => context.count})}</p>
<p>
    <div>
${
    context.deleted_options_count === 1
        ? html` ${$t({defaultMessage: "Deleted option:"})} `
        : html` ${$t({defaultMessage: "Deleted options:"})} `
}    </div>
    <ul>
${to_array(context.deleted_values).map((value) => html` <li>${value}</li> `)}    </ul>
</p>
`;
    return to_html(out);
}
