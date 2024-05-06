import $ from "jquery";
import {z} from "zod";

import render_settings_resend_invite_modal from "../templates/confirm_dialog/confirm_resend_invite.hbs";
import render_settings_revoke_invite_modal from "../templates/confirm_dialog/confirm_revoke_invite.hbs";
import render_admin_invites_list from "../templates/settings/admin_invites_list.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import {current_user, realm} from "./state_data";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as util from "./util";

export const invite_schema = z.intersection(
    z.object({
        invited_by_user_id: z.number(),
        invited: z.number(),
        expiry_date: z.number().nullable(),
        id: z.number(),
        invited_as: z.number(),
    }),
    z.discriminatedUnion("is_multiuse", [
        z.object({
            is_multiuse: z.literal(false),
            email: z.string(),
        }),
        z.object({
            is_multiuse: z.literal(true),
            link_url: z.string(),
        }),
    ]),
);
type Invite = z.output<typeof invite_schema> & {
    invited_as_text?: string;
    invited_absolute_time?: string;
    expiry_date_absolute_time?: string;
    is_admin?: boolean;
    disable_buttons?: boolean;
    referrer_name?: string;
    img_src?: string;
};

const meta = {
    loaded: false,
};

export function reset(): void {
    meta.loaded = false;
}

function failed_listing_invites(xhr: JQuery.jqXHR): void {
    loading.destroy_indicator($("#admin_page_invites_loading_indicator"));
    ui_report.error(
        $t_html({defaultMessage: "Error listing invites"}),
        xhr,
        $("#invites-field-status"),
    );
}

function add_invited_as_text(invites: Invite[]): void {
    for (const data of invites) {
        data.invited_as_text = settings_config.user_role_map.get(data.invited_as);
    }
}

function sort_invitee(a: Invite, b: Invite): number {
    // multi-invite links don't have an email field,
    // so we set them to empty strings to let them
    // sort to the top
    const str1 = a.is_multiuse ? "" : a.email.toUpperCase();
    const str2 = b.is_multiuse ? "" : b.email.toUpperCase();

    return util.strcmp(str1, str2);
}

function populate_invites(invites_data: {invites: Invite[]}): void {
    if (!meta.loaded) {
        return;
    }

    add_invited_as_text(invites_data.invites);

    const $invites_table = $("#admin_invites_table").expectOne();
    ListWidget.create($invites_table, invites_data.invites, {
        name: "admin_invites_list",
        get_item: ListWidget.default_get_item,
        modifier_html(item) {
            item.invited_absolute_time = timerender.absolute_time(item.invited * 1000);
            if (item.expiry_date !== null) {
                item.expiry_date_absolute_time = timerender.absolute_time(item.expiry_date * 1000);
            }
            item.is_admin = current_user.is_admin;
            item.disable_buttons =
                item.invited_as === settings_config.user_role_values.owner.code &&
                !current_user.is_owner;
            item.referrer_name = people.get_by_user_id(item.invited_by_user_id).full_name;
            item.img_src = people.small_avatar_url_for_person(
                people.get_by_user_id(item.invited_by_user_id),
            );
            return render_admin_invites_list({invite: item});
        },
        filter: {
            $element: $invites_table
                .closest(".settings-section")
                .find<HTMLInputElement>("input.search"),
            predicate(item, value) {
                const referrer = people.get_by_user_id(item.invited_by_user_id);
                const referrer_email = referrer.email;
                const referrer_name = referrer.full_name;
                const referrer_name_matched = referrer_name.toLowerCase().includes(value);
                const referrer_email_matched = referrer_email.toLowerCase().includes(value);
                if (item.is_multiuse) {
                    return referrer_name_matched || referrer_email_matched;
                }
                const invitee_email_matched = item.email.toLowerCase().includes(value);
                return referrer_email_matched || referrer_name_matched || invitee_email_matched;
            },
        },
        $parent_container: $("#admin-invites-list").expectOne(),
        init_sort: sort_invitee,
        sort_fields: {
            invitee: sort_invitee,
            ...ListWidget.generic_sort_functions("alphabetic", ["referrer_name"]),
            ...ListWidget.generic_sort_functions("numeric", [
                "invited",
                "expiry_date",
                "invited_as",
            ]),
        },
        $simplebar_container: $("#admin-invites-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_invites_loading_indicator"));
}

function do_revoke_invite({
    $row,
    invite_id,
    is_multiuse,
}: {
    $row: JQuery;
    invite_id: string;
    is_multiuse: string;
}): void {
    const modal_invite_id = $(".dialog_submit_button").attr("data-invite-id");
    const modal_is_multiuse = $(".dialog_submit_button").attr("data-is-multiuse");
    const $revoke_button = $row.find("button.revoke");

    if (modal_invite_id !== invite_id || modal_is_multiuse !== is_multiuse) {
        blueslip.error("Invite revoking canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Resending encountered an error. Please reload and try again.",
            }),
            $("#home-error"),
        );
    }

    $revoke_button.prop("disabled", true).text($t({defaultMessage: "Working…"}));
    let url = "/json/invites/" + invite_id;

    if (modal_is_multiuse === "true") {
        url = "/json/invites/multiuse/" + invite_id;
    }
    void channel.del({
        url,
        error(xhr) {
            ui_report.generic_row_button_error(xhr, $revoke_button);
        },
        success() {
            $row.remove();
        },
    });
}

function do_resend_invite({$row, invite_id}: {$row: JQuery; invite_id: string}): void {
    const modal_invite_id = $(".dialog_submit_button").attr("data-invite-id");
    const $resend_button = $row.find("button.resend");

    if (modal_invite_id !== invite_id) {
        blueslip.error("Invite resending canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Resending encountered an error. Please reload and try again.",
            }),
            $("#home-error"),
        );
    }

    $resend_button.prop("disabled", true).text($t({defaultMessage: "Working…"}));
    void channel.post({
        url: "/json/invites/" + invite_id + "/resend",
        error(xhr) {
            ui_report.generic_row_button_error(xhr, $resend_button);
        },
        success() {
            $resend_button.text($t({defaultMessage: "Sent!"}));
            $resend_button.removeClass("resend btn-warning").addClass("sea-green");
        },
    });
}

export function set_up(initialize_event_handlers = true): void {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($("#admin_page_invites_loading_indicator"));

    // Populate invites table
    void channel.get({
        url: "/json/invites",
        timeout: 10 * 1000,
        success(raw_data) {
            const data = z.object({invites: z.array(invite_schema)}).parse(raw_data);
            on_load_success(data, initialize_event_handlers);
        },
        error: failed_listing_invites,
    });
}

export function on_load_success(
    invites_data: {invites: Invite[]},
    initialize_event_handlers: boolean,
): void {
    meta.loaded = true;
    populate_invites(invites_data);
    if (!initialize_event_handlers) {
        return;
    }
    $(".admin_invites_table").on("click", ".revoke", function (this: HTMLElement, e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();
        const $row = $(this).closest(".invite_row");
        const email = $row.find(".email").text();
        const referred_by = $row.find(".referred_by").text();
        const invite_id = $(this).attr("data-invite-id")!;
        const is_multiuse = $(this).attr("data-is-multiuse")!;
        const ctx = {
            is_multiuse: is_multiuse === "true",
            email,
            referred_by,
        };
        const html_body = render_settings_revoke_invite_modal(ctx);

        confirm_dialog.launch({
            html_heading: ctx.is_multiuse
                ? $t_html({defaultMessage: "Revoke invitation link"})
                : $t_html({defaultMessage: "Revoke invitation to {email}"}, {email}),
            html_body,
            on_click() {
                do_revoke_invite({$row, invite_id, is_multiuse});
            },
        });

        $(".dialog_submit_button").attr("data-invite-id", invite_id);
        $(".dialog_submit_button").attr("data-is-multiuse", is_multiuse);
    });

    $(".admin_invites_table").on("click", ".resend", function (this: HTMLElement, e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        const $row = $(this).closest(".invite_row");
        const email = $row.find(".email").text();
        const invite_id = $(this).attr("data-invite-id")!;
        const html_body = render_settings_resend_invite_modal({email});

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Resend invitation?"}),
            html_body,
            on_click() {
                do_resend_invite({$row, invite_id});
            },
        });

        $(".dialog_submit_button").attr("data-invite-id", invite_id);
    });
}

export function update_invite_users_setting_tip(): void {
    if (settings_data.user_can_invite_users_by_email() && !current_user.is_admin) {
        $(".invite-user-settings-tip").hide();
        return;
    }
    const permission_type = settings_config.email_invite_to_realm_policy_values;
    const current_permission = realm.realm_invite_to_realm_policy;
    let tip_text;
    switch (current_permission) {
        case permission_type.by_admins_only.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins can invite users to this organization.",
            });

            break;
        }
        case permission_type.by_moderators_only.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins and moderators can invite users to this organization.",
            });

            break;
        }
        case permission_type.by_members.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins, moderators and members can invite users to this organization.",
            });

            break;
        }
        case permission_type.by_full_members.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins, moderators and full members can invite users to this organization.",
            });

            break;
        }
        default: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that nobody can invite users to this organization.",
            });
        }
    }
    $(".invite-user-settings-tip").show();
    $(".invite-user-settings-tip").text(tip_text);
}

export function update_invite_user_panel(): void {
    update_invite_users_setting_tip();
    if (
        !settings_data.user_can_invite_users_by_email() &&
        !settings_data.user_can_create_multiuse_invite()
    ) {
        $("#admin-invites-list .invite-user-link").hide();
    } else {
        $("#admin-invites-list .invite-user-link").show();
    }
}
