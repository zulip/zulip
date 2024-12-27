import $ from "jquery";
import {z} from "zod";

import render_settings_resend_invite_modal from "../templates/confirm_dialog/confirm_resend_invite.hbs";
import render_settings_revoke_invite_modal from "../templates/confirm_dialog/confirm_revoke_invite.hbs";
import render_edit_invite_user_modal from "../templates/edit_invite_user_modal.hbs";
import render_admin_invites_list from "../templates/settings/admin_invites_list.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import {set_streams_to_join_list_visibility} from "./invite.ts";
import * as invite_stream_picker_pill from "./invite_stream_picker_pill.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as people from "./people.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_pill from "./stream_pill.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

export const invite_schema = z.intersection(
    z.object({
        invited_by_user_id: z.number(),
        invited: z.number(),
        expiry_date: z.number().nullable(),
        id: z.number(),
        invited_as: z.number(),
        stream_ids: z.array(z.number()),
        include_realm_default_subscriptions: z.boolean(),
    }),
    z.discriminatedUnion("is_multiuse", [
        z.object({
            is_multiuse: z.literal(false),
            email: z.string(),
            notify_referrer_on_join: z.boolean(),
        }),
        z.object({
            is_multiuse: z.literal(true),
            link_url: z.string(),
            stream_ids: z.array(z.number()),
        }),
    ]),
);
type Invite = z.output<typeof invite_schema> & {
    invited_as_text?: string | undefined;
    invited_absolute_time?: string;
    expiry_date_absolute_time?: string;
    is_admin?: boolean;
    disable_buttons?: boolean;
    referrer_name?: string;
    img_src?: string;
    notify_referrer_on_join?: boolean;
};

type Meta = {
    loaded: boolean;
    invites: Invite[];
};

const meta: Meta = {
    loaded: false,
    invites: [],
};

let stream_pill_widget: stream_pill.StreamPillWidget;

export function reset(): void {
    meta.loaded = false;
    meta.invites = [];
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

    meta.invites = invites_data.invites;
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
            if (item.is_multiuse && !settings_data.user_can_create_multiuse_invite()) {
                item.disable_buttons = true;
            }
            return render_admin_invites_list({invite: item});
        },
        filter: {
            $element: $invites_table
                .closest(".user-settings-section")
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

    if (modal_invite_id !== invite_id || modal_is_multiuse !== is_multiuse) {
        blueslip.error("Invite revoking canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Error: Could not revoke invitation.",
            }),
            $("#revoke_invite_modal #dialog_error"),
        );
        dialog_widget.hide_dialog_spinner();
        return;
    }

    let url = "/json/invites/" + invite_id;

    if (modal_is_multiuse === "true") {
        url = "/json/invites/multiuse/" + invite_id;
    }
    void channel.del({
        url,
        error(xhr) {
            dialog_widget.hide_dialog_spinner();
            ui_report.error(
                $t_html({
                    defaultMessage: "Failed",
                }),
                xhr,
                $("#dialog_error"),
            );
        },
        success() {
            dialog_widget.hide_dialog_spinner();
            dialog_widget.close();
            $row.remove();
        },
    });
}

function do_resend_invite({$row, invite_id}: {$row: JQuery; invite_id: string}): void {
    const modal_invite_id = $(".dialog_submit_button").attr("data-invite-id");
    const $resend_button = $row.find("button.resend");
    const $check_button = $row.find("button.check");

    if (modal_invite_id !== invite_id) {
        blueslip.error("Invite resending canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Error: Could not resend invitation.",
            }),
            $("#resend_invite_modal #dialog_error"),
        );
        dialog_widget.hide_dialog_spinner();
        return;
    }

    void channel.post({
        url: "/json/invites/" + invite_id + "/resend",
        error(xhr) {
            dialog_widget.hide_dialog_spinner();
            ui_report.error(
                $t_html({
                    defaultMessage: "Failed",
                }),
                xhr,
                $("#dialog_error"),
            );
        },
        success() {
            dialog_widget.hide_dialog_spinner();
            dialog_widget.close();

            $resend_button.hide();
            $check_button.removeClass("hide");

            // Showing a success checkmark for a short time (3 seconds).
            setTimeout(() => {
                $resend_button.show();
                $check_button.addClass("hide");
            }, 3000);
        },
    });
}

type GetInvitationData = {
    csrfmiddlewaretoken: string | undefined;
    invite_as: number;
    stream_ids: string;
};

function get_invitation_data(): GetInvitationData {
    const invite_as = Number.parseInt(String($("#invite_as").val()), 10);

    let stream_ids: number[] = [];
    let include_realm_default_subscriptions = false;
    if (
        $("#invite_select_default_streams").prop("checked") ||
        !settings_data.can_subscribe_others_to_all_accessible_streams()
    ) {
        include_realm_default_subscriptions = true;
    } else {
        stream_ids = stream_pill.get_stream_ids(stream_pill_widget);
    }

    const data = {
        csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').attr("value"),
        invite_as,
        stream_ids: JSON.stringify(stream_ids),
        include_realm_default_subscriptions: JSON.stringify(include_realm_default_subscriptions),
    };
    return data;
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
        // will not show up because of a call to `close_active` in `settings.ts`.
        e.preventDefault();
        e.stopPropagation();
        const $row = $(this).closest(".invite_row");
        const email = $row.find(".email").text();
        const referred_by = $row.find(".referred_by").text();
        const invite_id = $(this).closest("tr").attr("data-invite-id")!;
        const is_multiuse = $(this).closest("tr").attr("data-is-multiuse")!;
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
            id: "revoke_invite_modal",
            close_on_submit: false,
            loading_spinner: true,
            on_click() {
                do_revoke_invite({$row, invite_id, is_multiuse});
            },
        });

        $(".dialog_submit_button").attr("data-invite-id", invite_id);
        $(".dialog_submit_button").attr("data-is-multiuse", is_multiuse);
    });

    $(".admin_invites_table").on("click", ".resend", function (this: HTMLElement, e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active` in `settings.ts`.
        e.preventDefault();
        e.stopPropagation();

        const $row = $(this).closest(".invite_row");
        const email = $row.find(".email").text();
        const invite_id = $(this).closest("tr").attr("data-invite-id")!;
        const html_body = render_settings_resend_invite_modal({email});

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Resend invitation?"}),
            html_body,
            id: "resend_invite_modal",
            close_on_submit: false,
            loading_spinner: true,
            on_click() {
                do_resend_invite({$row, invite_id});
            },
        });

        $(".dialog_submit_button").attr("data-invite-id", invite_id);
    });

    $(".admin_invites_table").on("click", ".edit-invite", function (this: HTMLElement, e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        const invite_id = $(this).attr("data-invite-id")!;
        $(".dialog_submit_button").attr("data-invite-id", invite_id);
        const invite: Invite | undefined = meta.invites.find(
            (invite) => invite.id === Number.parseInt(invite_id, 10) && invite.is_multiuse,
        );
        const html_body = render_edit_invite_user_modal({
            invite_as_options: settings_config.user_role_values,
            is_admin: current_user.is_admin,
            is_owner: current_user.is_owner,
            show_select_default_streams_option: stream_data.get_default_stream_ids().length > 0,
            can_subscribe_other_users:
                settings_data.can_subscribe_others_to_all_accessible_streams(),
        });

        function edit_invite_user_modal_post_render(): void {
            const $submit_button = $("#edit-invite-form .dialog_submit_button");
            $submit_button.prop("disabled", true);
            $submit_button.attr("data-loading-text", $t({defaultMessage: "Updating link…"}));
            if (invite?.is_multiuse) {
                const $stream_pill_container = $("#invite_streams_container .pill-container");
                if (invite.include_realm_default_subscriptions) {
                    $("#invite_select_default_streams").prop("checked", true);
                    $(".add_streams_container").hide();
                } else {
                    $("#invite_select_default_streams").prop("checked", false);
                    $(".add_streams_container").show();
                }
                stream_pill_widget = invite_stream_picker_pill.create(
                    $stream_pill_container,
                    invite.stream_ids,
                );
                $("#invite_as").val(invite.invited_as);
            }

            function toggle_submit_button($elem: JQuery): void {
                if (!invite || !invite.is_multiuse) {
                    $elem.prop("disabled", true);
                    return;
                }
                const initial_streams = [...invite.stream_ids].sort();
                let selected_streams: number[] = [];
                if (!$("#invite_select_default_streams").prop("checked")) {
                    selected_streams = stream_pill.get_stream_ids(stream_pill_widget).sort();
                }
                const is_state_unchanged =
                    selected_streams.length === initial_streams.length &&
                    selected_streams.every((val, index) => val === initial_streams[index]) &&
                    Number.parseInt(String($("#invite_as").val()), 10) === invite.invited_as &&
                    $("#invite_select_default_streams").prop("checked") ===
                        invite.include_realm_default_subscriptions;

                $elem.prop("disabled", is_state_unchanged);
            }

            $("#edit-invite-form").on("change", "#invite_as, div.input", () => {
                e.preventDefault();
                toggle_submit_button($submit_button);
            });
            $("#invite_select_default_streams").on("change", () => {
                e.preventDefault();
                set_streams_to_join_list_visibility();
                toggle_submit_button($submit_button);
            });
        }

        function do_edit_invite(): void {
            const $invite_status = $("#dialog_error");
            const data = get_invitation_data();

            void channel.patch({
                url: `/json/invites/multiuse/${invite_id}`,
                data,
                success() {
                    dialog_widget.close();
                },
                error(xhr) {
                    ui_report.error(xhr.responseText, xhr, $invite_status);
                },
                complete() {
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Edit invite"}),
            html_body,
            html_submit_button: $t_html({defaultMessage: "Save changes"}),
            id: "edit-invite-form",
            loading_spinner: true,
            on_click: do_edit_invite,
            post_render: edit_invite_user_modal_post_render,
            help_link: "/help/invite-new-users#edit-a-reusable-invitation-link",
        });
    });
}

export function update_invite_users_setting_tip(): void {
    if (settings_data.user_can_invite_users_by_email()) {
        $(".invite-user-settings-tip").hide();
        return;
    }

    $(".invite-user-settings-tip").show();
    $(".invite-user-settings-tip").text(
        $t({
            defaultMessage:
                "You do not have permission to send invite emails in this organization.",
        }),
    );
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
