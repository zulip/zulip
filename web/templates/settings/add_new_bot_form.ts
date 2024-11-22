import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_embedded_bot_config_item from "../embedded_bot_config_item.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_add_new_bot_form(context) {
    const out = html`<form id="create_bot_form">
    <div class="new-bot-form">
        <div class="input-group">
            <label for="create_bot_type" class="modal-field-label">
                ${$t({defaultMessage: "Bot type"})}
                ${{__html: render_help_link_widget({link: "/help/bots-overview#bot-type"})}}            </label>
            <select name="bot_type" id="create_bot_type" class="modal_select bootstrap-focus-style">
${to_array(context.bot_types).map((bot_type) =>
    to_bool(bot_type.allowed)
        ? html` <option value="${bot_type.type_id}">${bot_type.name}</option> `
        : "",
)}            </select>
        </div>
        <div class="input-group" id="service_name_list">
            <label for="select_service_name" class="modal-field-label">${$t({defaultMessage: "Bot"})}</label>
            <select name="service_name" id="select_service_name" class="modal_select bootstrap-focus-style">
${to_array(context.realm_embedded_bots).map(
    (bot) => html` <option value="${bot.name}">${bot.name}</option> `,
)}            </select>
        </div>
        <div class="input-group">
            <label for="create_bot_name" class="modal-field-label">${$t({defaultMessage: "Name"})}</label>
            <input type="text" name="bot_name" id="create_bot_name" class="required modal_text_input"
              maxlength=100 placeholder="${$t({defaultMessage: "Cookie Bot"})}" value="" />
            <div><label for="create_bot_name" generated="true" class="text-error"></label></div>
        </div>
        <div class="input-group">
            <label for="create_bot_short_name" class="modal-field-label">${$t({defaultMessage: "Bot email (a-z, 0-9, and dashes only)"})}</label>
            <input type="text" name="bot_short_name" id="create_bot_short_name" class="required bot_local_part modal_text_input"
              placeholder="${$t({defaultMessage: "cookie"})}" value="" />
            -bot@${context.realm_bot_domain}
            <div>
                <label for="create_bot_short_name" generated="true" class="text-error"></label>
            </div>
        </div>
        <div id="payload_url_inputbox">
            <div class="input-group">
                <label for="create_payload_url" class="modal-field-label">${$t({defaultMessage: "Endpoint URL"})}</label>
                <input type="text" name="payload_url" id="create_payload_url" class="modal_text_input"
                  maxlength=2083 placeholder="https://hostname.example.com" value="" />
                <div><label for="create_payload_url" generated="true" class="text-error"></label></div>
            </div>
            <div class="input-group">
                <label for="interface_type" class="modal-field-label">${$t({defaultMessage: "Outgoing webhook message format"})}</label>
                <select name="interface_type" id="create_interface_type" class="modal_select bootstrap-focus-style">
                    <option value="1">Zulip</option>
                    <option value="2">${$t({defaultMessage: "Slack compatible"})}</option>
                </select>
                <div><label for="create_interface_type" generated="true" class="text-error"></label></div>
            </div>
        </div>
        <div id="config_inputbox">
${to_array(context.realm_embedded_bots).map((bot) => Object.entries(bot.config).map(([context2_key, context2]) => html` ${{__html: render_embedded_bot_config_item({value: context2, key: context2_key, botname: bot.name})}}`))}        </div>
        <div class="input-group">
            <label for="bot_avatar_file_input" class="modal-field-label">${$t({defaultMessage: "Avatar"})}</label>
            <div id="bot_avatar_file"></div>
            <input type="file" name="bot_avatar_file_input" class="notvisible" id="bot_avatar_file_input" value="${$t({defaultMessage: "Upload avatar"})}" />
            <div id="add_bot_preview_text">
                <img id="add_bot_preview_image" />
            </div>
            <button class="button white rounded small button-danger" style="display: none;" id="bot_avatar_clear_button">${$t({defaultMessage: "Clear avatar"})}</button>
            <button class="button white rounded" id="bot_avatar_upload_button">${$t({defaultMessage: "Choose avatar"})}</button> (${$t({defaultMessage: "Optional"})})
        </div>
        <p>
            <div id="bot_avatar_file_input_error" class="text-error"></div>
        </p>
    </div>
</form>
`;
    return to_html(out);
}
