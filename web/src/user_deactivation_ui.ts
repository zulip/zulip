import $ from "jquery";
import * as z from "zod/mini";

import render_settings_deactivation_bot_modal from "../templates/confirm_dialog/confirm_deactivate_bot.hbs";
import render_confirm_deactivate_own_user from "../templates/confirm_dialog/confirm_deactivate_own_user.hbs";
import render_settings_deactivation_user_modal from "../templates/confirm_dialog/confirm_deactivate_user.hbs";
import render_settings_reactivation_bot_modal from "../templates/confirm_dialog/confirm_reactivate_bot.hbs";
import render_settings_reactivation_user_modal from "../templates/confirm_dialog/confirm_reactivate_user.hbs";

import * as bot_data from "./bot_data.ts";
import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t_html} from "./i18n.ts";
import * as people from "./people.ts";
import {invite_schema} from "./settings_invites.ts";
import {current_user, realm} from "./state_data.ts";

export function confirm_deactivation(
    user_id: number,
    handle_confirm: () => void,
    loading_spinner: boolean,
): void {
    if (user_id === current_user.user_id) {
        const html_body = render_confirm_deactivate_own_user();
        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Deactivate your account"}),
            html_body,
            on_click: handle_confirm,
            help_link: "/help/deactivate-your-account",
            loading_spinner,
        });
        return;
    }

    // Knowing the number of invites requires making this request. If the request fails,
    // we won't have the accurate number of invites. So, we don't show the modal if the
    // request fails.
    void channel.get({
        url: "/json/invites",
        timeout: 10 * 1000,
        success(raw_data) {
            const data = z.object({invites: z.array(invite_schema)}).parse(raw_data);

            let number_of_invites_by_user = 0;
            for (const invite of data.invites) {
                if (invite.invited_by_user_id === user_id) {
                    number_of_invites_by_user = number_of_invites_by_user + 1;
                }
            }

            const bots_owned_by_user = bot_data.get_all_bots_owned_by_user(user_id);
            const user = people.get_by_user_id(user_id);
            const realm_url = realm.realm_url;
            const realm_name = realm.realm_name;
            const opts = {
                username: user.full_name,
                email: user.delivery_email,
                bots_owned_by_user,
                number_of_invites_by_user,
                admin_email: people.my_current_email(),
                realm_url,
                realm_name,
            };
            const html_body = render_settings_deactivation_user_modal(opts);

            function set_email_field_visibility(dialog_widget_id: string): void {
                const $modal = $(`#${CSS.escape(dialog_widget_id)}`);
                const $send_email_checkbox = $modal.find(".send_email");
                const $email_field = $modal.find(".email_field");

                $email_field.hide();
                $send_email_checkbox.on("change", () => {
                    if ($send_email_checkbox.is(":checked")) {
                        $email_field.show();
                    } else {
                        $email_field.hide();
                    }
                });
            }

            dialog_widget.launch({
                html_heading: $t_html(
                    {defaultMessage: "Deactivate {name}?"},
                    {name: user.full_name},
                ),
                help_link: "/help/deactivate-or-reactivate-a-user#deactivating-a-user",
                html_body,
                html_submit_button: $t_html({defaultMessage: "Deactivate"}),
                id: "deactivate-user-modal",
                on_click: handle_confirm,
                post_render: set_email_field_visibility,
                loading_spinner,
                focus_submit_on_open: true,
            });
        },
    });
}

export function confirm_bot_deactivation(
    bot_id: number,
    handle_confirm: () => void,
    loading_spinner: boolean,
): void {
    const bot = people.get_by_user_id(bot_id);
    const html_body = render_settings_deactivation_bot_modal();

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Deactivate {name}?"}, {name: bot.full_name}),
        help_link: "/help/deactivate-or-reactivate-a-bot",
        html_body,
        html_submit_button: $t_html({defaultMessage: "Deactivate"}),
        on_click: handle_confirm,
        loading_spinner,
    });
}

export function confirm_reactivation(
    user_id: number,
    handle_confirm: () => void,
    loading_spinner: boolean,
): void {
    const user = people.get_by_user_id(user_id);
    const opts: {
        username: string;
        original_owner_deactivated?: boolean;
        owner_name?: string;
    } = {
        username: user.full_name,
    };

    let html_body;
    // check if bot or human
    if (user.is_bot) {
        if (user.bot_owner_id !== null && !people.is_person_active(user.bot_owner_id)) {
            opts.original_owner_deactivated = true;
            opts.owner_name = people.get_by_user_id(user.bot_owner_id).full_name;
        } else {
            opts.original_owner_deactivated = false;
        }
        html_body = render_settings_reactivation_bot_modal(opts);
    } else {
        html_body = render_settings_reactivation_user_modal(opts);
    }

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Reactivate {name}"}, {name: user.full_name}),
        help_link: "/help/deactivate-or-reactivate-a-user#reactivating-a-user",
        html_body,
        on_click: handle_confirm,
        loading_spinner,
    });
}
