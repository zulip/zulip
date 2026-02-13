import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_settings_resend_invite_modal from "../templates/confirm_dialog/confirm_resend_invite.hbs";
import render_settings_revoke_invite_modal from "../templates/confirm_dialog/confirm_revoke_invite.hbs";
import render_edit_invite_user_modal from "../templates/edit_invite_user_modal.hbs";
import render_admin_invites_list from "../templates/settings/admin_invites_list.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as invite from "./invite.ts";
import * as invite_stream_picker_pill from "./invite_stream_picker_pill.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as people from "./people.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_pill from "./stream_pill.ts";
import * as timerender from "./timerender.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import * as user_group_picker_pill from "./user_group_picker_pill.ts";
import * as user_group_pill from "./user_group_pill.ts";
import * as user_groups from "./user_groups.ts";
import * as util from "./util.ts";

export const invite_schema = z.intersection(
    z.object({
        invited_by_user_id: z.number(),
        invited: z.number(),
        expiry_date: z.nullable(z.number()),
        id: z.number(),
        invited_as: z.number(),
        stream_ids: z.array(z.number()),
        group_ids: z.array(z.number()),
        include_realm_default_subscriptions: z.boolean(),
        welcome_message_custom_text: z.nullable(z.string()),
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
        }),
    ]),
);
type Invite = z.output<typeof invite_schema> & {
    invited_as_text?: string | undefined;
    invited_absolute_time?: string;
    expiry_date_absolute_time?: string;
    is_admin?: boolean;
    disable_edit_button?: boolean;
    disable_revoke_and_resend_button?: boolean;
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
let user_group_pill_widget: user_group_pill.UserGroupPillWidget;

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
            item.disable_edit_button = !settings_data.user_can_create_multiuse_invite();
            item.disable_revoke_and_resend_button =
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

type InvitationData = {
    csrfmiddlewaretoken: string | undefined;
    invite_as: number;
    stream_ids: string;
    group_ids?: string;
    include_realm_default_subscriptions: string;
    welcome_message_custom_text?: string;
};

function validate_stream_ids_for_invitation(stream_ids: number[]): boolean {
    for (const stream_id of stream_ids) {
        const sub = stream_data.get_sub_by_id(stream_id)!;
        if (sub.is_archived) {
            ui_report.message(
                $t_html(
                    {defaultMessage: "Failed: <b>#{stream_name}</b> is archived."},
                    {stream_name: sub.name},
                ),
                $("#dialog_error"),
                "alert-error",
            );
            return false;
        }

        if (
            !stream_data.is_default_stream_id(stream_id) &&
            !stream_data.can_subscribe_others(sub)
        ) {
            ui_report.message(
                $t_html(
                    {
                        defaultMessage:
                            "Failed: You are not allowed to subscribe others to <b>#{stream_name}</b>.",
                    },
                    {stream_name: sub.name},
                ),
                $("#dialog_error"),
                "alert-error",
            );
            return false;
        }
    }
    return true;
}

function validate_group_ids_for_invitation(group_ids: number[]): boolean {
    for (const group_id of group_ids) {
        const user_group = user_groups.get_user_group_from_id(group_id);
        if (user_group.deactivated) {
            ui_report.message(
                $t_html(
                    {defaultMessage: "Failed: <b>{group_name}</b> is deactivated."},
                    {group_name: user_group.name},
                ),
                $("#dialog_error"),
                "alert-error",
            );
            return false;
        }

        if (!settings_data.can_add_members_to_user_group(group_id)) {
            ui_report.message(
                $t_html(
                    {
                        defaultMessage:
                            "Failed: You are not allowed to add users to <b>{group_name}</b>.",
                    },
                    {group_name: user_group.name},
                ),
                $("#dialog_error"),
                "alert-error",
            );
            return false;
        }
    }
    return true;
}

function get_invitation_data(): InvitationData | undefined {
    const invite_as = Number.parseInt(
        $<HTMLSelectOneElement>("select:not([multiple])#invite_as").val()!,
        10,
    );

    const include_realm_default_subscriptions = $("#invite_select_default_streams").is(":checked");
    let stream_ids: number[] = [];
    if (!include_realm_default_subscriptions || stream_data.get_default_stream_ids().length === 0) {
        stream_ids = stream_pill.get_stream_ids(stream_pill_widget);

        if (!validate_stream_ids_for_invitation(stream_ids)) {
            return undefined;
        }
    }

    const data: InvitationData = {
        csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').attr("value"),
        invite_as,
        stream_ids: JSON.stringify(stream_ids),
        include_realm_default_subscriptions: JSON.stringify(include_realm_default_subscriptions),
    };

    if (user_group_pill_widget !== undefined) {
        const group_ids = user_group_pill.get_group_ids(user_group_pill_widget);

        if (!validate_group_ids_for_invitation(group_ids)) {
            return undefined;
        }

        data.group_ids = JSON.stringify(group_ids);
    }

    if (current_user.is_admin) {
        data.welcome_message_custom_text = JSON.stringify(
            invite.get_welcome_message_custom_text_value(),
        );
    }

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

function set_welcome_message_custom_text_ui(current_value: string | null): void {
    if (!current_user.is_admin) {
        return;
    }

    const realm_welcome_message_configured = realm.realm_welcome_message_custom_text.length > 0;
    if (current_value === null) {
        $("#invite_welcome_message_custom_text_container").hide();
        if (realm_welcome_message_configured) {
            $("#send_default_realm_welcome_message_custom_text").prop("checked", true);
        } else {
            $("#send_custom_welcome_message_custom_text").prop("checked", false);
        }
        return;
    }

    $("#invite_welcome_message_custom_text_container").show();
    $("#invite_welcome_message_custom_text_container textarea").val(current_value);
    if (realm_welcome_message_configured) {
        $("#send_default_realm_welcome_message_custom_text").prop("checked", false);
    } else {
        $("#send_custom_welcome_message_custom_text").prop("checked", true);
    }
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
        const modal_content_html = render_settings_revoke_invite_modal(ctx);

        confirm_dialog.launch({
            modal_title_html: ctx.is_multiuse
                ? $t_html({defaultMessage: "Revoke invitation link"})
                : $t_html({defaultMessage: "Revoke invitation to {email}"}, {email}),
            modal_content_html,
            is_compact: true,
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
        const modal_content_html = render_settings_resend_invite_modal({email});

        confirm_dialog.launch({
            modal_title_html: $t_html({defaultMessage: "Resend invitation?"}),
            modal_content_html,
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

        const invite_id = $(this).closest("tr").attr("data-invite-id")!;

        $(".dialog_submit_button").closest("tr").attr("data-invite-id", invite_id);
        const multiuse_invite = meta.invites.find(
            (invite) => invite.id === Number(invite_id) && invite.is_multiuse,
        );
        assert(multiuse_invite !== undefined);
        const creator = people.get_by_user_id(multiuse_invite.invited_by_user_id);
        const invite_as_options = invite.get_invite_as_options_for_invite(
            creator,
            multiuse_invite.invited_as,
        );
        const show_group_pill_container =
            user_groups.get_realm_user_groups().length > 0 || multiuse_invite.group_ids.length > 0;
        const realm_has_default_streams = stream_data.get_default_stream_ids().length > 0;
        const modal_content_html = render_edit_invite_user_modal({
            invite_as_options,
            is_admin: current_user.is_admin,
            is_owner: current_user.is_owner,
            show_group_pill_container,
            show_select_default_streams_option:
                multiuse_invite.include_realm_default_subscriptions || realm_has_default_streams,
            default_welcome_message_custom_text: realm.realm_welcome_message_custom_text,
        });

        function edit_invite_user_modal_post_render(): void {
            const $submit_button = $("#edit-invite-form .dialog_submit_button");
            $submit_button.prop("disabled", true);
            $submit_button.attr("data-loading-text", $t({defaultMessage: "Updating link…"}));

            assert(multiuse_invite !== undefined);
            $("#invite_select_default_streams").prop(
                "checked",
                multiuse_invite.include_realm_default_subscriptions,
            );
            invite.set_streams_to_join_list_visibility();

            const $stream_pill_container = $("#invite_streams_container .pill-container");
            stream_pill_widget = invite_stream_picker_pill.create(
                $stream_pill_container,
                multiuse_invite.stream_ids,
            );
            if (multiuse_invite.include_realm_default_subscriptions) {
                if (realm_has_default_streams) {
                    invite_stream_picker_pill.add_default_stream_pills(stream_pill_widget);
                } else {
                    stream_pill_widget.onPillCreate(() => {
                        if ($("#invite_select_default_streams").is(":checked")) {
                            $("#invite_select_default_streams").prop("checked", false);
                        }
                    });
                }
            }

            $("#invite_as").val(multiuse_invite.invited_as);

            set_welcome_message_custom_text_ui(multiuse_invite.welcome_message_custom_text);

            if (show_group_pill_container) {
                const $user_group_pill_container = $(
                    "#edit-invite-form #invite-user-group-container .pill-container",
                );
                user_group_pill_widget = user_group_picker_pill.create(
                    $user_group_pill_container,
                    undefined,
                    multiuse_invite.group_ids,
                );
            }

            function toggle_submit_button($elem: JQuery): void {
                if (!multiuse_invite) {
                    $elem.prop("disabled", true);
                    return;
                }
                const initial_streams = new Set(multiuse_invite.stream_ids);
                let selected_streams = new Set();
                if (!$("#invite_select_default_streams").prop("checked")) {
                    selected_streams = new Set(stream_pill.get_stream_ids(stream_pill_widget));
                }

                const initial_groups = new Set(multiuse_invite.group_ids || []);
                let selected_groups = new Set();
                if (user_group_pill_widget) {
                    selected_groups = new Set(
                        user_group_pill.get_group_ids(user_group_pill_widget),
                    );
                }

                // Check if welcome message has changed
                let welcome_message_changed = false;
                if (current_user.is_admin) {
                    welcome_message_changed =
                        invite.get_welcome_message_custom_text_value() !==
                        multiuse_invite.welcome_message_custom_text;
                }

                const is_state_unchanged =
                    _.isEqual(initial_streams, selected_streams) &&
                    _.isEqual(initial_groups, selected_groups) &&
                    Number.parseInt(String($("#invite_as").val()), 10) ===
                        multiuse_invite.invited_as &&
                    $("#invite_select_default_streams").prop("checked") ===
                        multiuse_invite.include_realm_default_subscriptions &&
                    !welcome_message_changed;

                $elem.prop("disabled", is_state_unchanged);
            }

            $("#edit-invite-form").on("change", "#invite_as, div.input", () => {
                e.preventDefault();
                toggle_submit_button($submit_button);
            });
            $("#invite_select_default_streams").on("change", () => {
                e.preventDefault();
                invite.set_streams_to_join_list_visibility();
                toggle_submit_button($submit_button);
            });
            $(
                "#send_default_realm_welcome_message_custom_text, #send_custom_welcome_message_custom_text",
            ).on("change", () => {
                invite.set_welcome_message_custom_text_visibility();
                toggle_submit_button($submit_button);
            });
            $("#invite_welcome_custom_message_text").on("input", () => {
                toggle_submit_button($submit_button);
            });
        }

        function do_edit_invite(): void {
            const $invite_status = $("#dialog_error");
            const data = get_invitation_data();

            if (data === undefined) {
                // There is some validation error, so we hide the
                // spinner on button and return.
                dialog_widget.hide_dialog_spinner();
                return;
            }

            void channel.patch({
                url: `/json/invites/multiuse/${invite_id}`,
                data,
                success() {
                    dialog_widget.close();
                },
                error(xhr) {
                    ui_report.error(
                        $t_html({
                            defaultMessage: "Failed",
                        }),
                        xhr,
                        $invite_status,
                    );
                },
                complete() {
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }

        dialog_widget.launch({
            modal_title_html: $t_html({defaultMessage: "Edit invite"}),
            modal_content_html,
            modal_submit_button_text: $t({defaultMessage: "Save changes"}),
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
        $(".invite-user-settings-banner").hide();
        return;
    }

    $(".invite-user-settings-banner").show();
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
