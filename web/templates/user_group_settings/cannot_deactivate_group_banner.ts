import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_cannot_deactivate_group_banner(context) {
    const out = html`<p>
    ${$t({defaultMessage: "This group cannot be deactivated because it is used in following places:"})}
    <ul>
${to_array(context.streams_using_group_for_setting).map((stream) =>
    to_bool(stream.setting_url)
        ? html` <li><a href="${stream.setting_url}">#${stream.stream_name}</a></li> `
        : html` <li>${stream.stream_name}</li> `,
)}${to_array(context.groups_using_group_for_setting).map(
        (group) => html` <li><a href="${group.setting_url}">@${group.group_name}</a></li> `,
    )}${
        to_bool(context.realm_using_group_for_setting)
            ? html`
                  <li>
                      <a href="#organization">${$t({defaultMessage: "Organization settings"})}</a>
                  </li>
              `
            : ""
    }    </ul>
</p>
`;
    return to_html(out);
}
