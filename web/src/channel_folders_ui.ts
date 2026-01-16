import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_confirm_archive_channel_folder from "../templates/confirm_dialog/confirm_archive_channel_folder.hbs";
import render_stream_list_item from "../templates/stream_list_item.hbs";
import render_create_channel_folder_modal from "../templates/stream_settings/create_channel_folder_modal.hbs";
import render_edit_channel_folder_modal from "../templates/stream_settings/edit_channel_folder_modal.hbs";

import * as banners from "./banners.ts";
import * as buttons from "./buttons.ts";
import * as channel from "./channel.ts";
import * as channel_folders from "./channel_folders.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {DropdownWidget, DropdownWidgetOptions} from "./dropdown_widget.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as modals from "./modals.ts";
import * as people from "./people.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

let channel_folder_stream_list_widget: ListWidgetType<StreamSubscription> | undefined;
let stream_list_widget_stream_ids: Set<number> | undefined;
let add_channel_folder_widget: DropdownWidget | undefined;

function compare_by_name(a: dropdown_widget.Option, b: dropdown_widget.Option): number {
    return util.strcmp(a.name, b.name);
}

function can_user_manage_folder(): boolean {
    return current_user.is_admin;
}

export function add_channel_folder(): void {
    const html_body = render_create_channel_folder_modal({
        max_channel_folder_name_length: realm.max_channel_folder_name_length,
        max_channel_folder_description_length: realm.max_channel_folder_description_length,
    });

    function create_channel_folder(): void {
        const close_on_success = true;
        const data = {
            name: $<HTMLInputElement>("input#new_channel_folder_name").val()!.trim(),
            description: $<HTMLTextAreaElement>("textarea#new_channel_folder_description")
                .val()!
                .trim(),
        };
        dialog_widget.submit_api_request(
            channel.post,
            "/json/channel_folders/create",
            data,
            {
                success_continuation(response_data) {
                    const id = z
                        .object({channel_folder_id: z.number()})
                        .parse(response_data).channel_folder_id;
                    // This is a temporary channel folder object added
                    // to channel folders data, so that the folder is
                    // immediately visible in the dropdown.
                    // This will be replaced with the actual object once
                    // the client receives channel_folder/add event.
                    const channel_folder = {
                        id,
                        name: data.name,
                        description: data.description,
                        is_archived: false,
                        rendered_description: "",
                        date_created: 0,
                        creator_id: people.my_current_user_id(),
                        order: id,
                    };
                    channel_folders.add(channel_folder);
                },
            },
            close_on_success,
        );
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Create channel folder"}),
        html_body,
        id: "create_channel_folder",
        html_submit_button: $t_html({defaultMessage: "Create"}),
        on_click: create_channel_folder,
        loading_spinner: true,
        on_shown: () => $("#new_channel_folder_name").trigger("focus"),
    });
}

function remove_channel_from_folder(
    stream_id: number,
    on_success: () => void,
    on_error: (xhr: JQuery.jqXHR) => void,
): void {
    const url = "/json/streams/" + stream_id.toString();
    const data = {
        folder_id: JSON.stringify(null),
    };
    void channel.patch({
        url,
        data,
        success: on_success,
        error: on_error,
    });
}

function add_channel_to_folder(
    stream_id: number,
    folder_id: number,
    on_success: () => void,
    on_error: (xhr: JQuery.jqXHR) => void,
): void {
    const url = "/json/streams/" + stream_id.toString();
    const data = {
        folder_id: JSON.stringify(folder_id),
    };
    void channel.patch({
        url,
        data,
        success: on_success,
        error: on_error,
    });
}

function archive_folder(folder_id: number): void {
    const stream_ids = channel_folders.get_stream_ids_in_folder(folder_id);
    let successful_requests = 0;

    function make_archive_folder_request(): void {
        const url = "/json/channel_folders/" + folder_id.toString();
        const data = {
            is_archived: JSON.stringify(true),
        };
        const opts = {
            success_continuation() {
                // Update the channel folders data so that
                // the folder dropdown shows only non-archived
                // folders immediately even if client receives
                // the update event after some delay.
                channel_folders.update_channel_folder(folder_id, "is_archived", true);
            },
        };
        dialog_widget.submit_api_request(channel.patch, url, data, opts);
    }

    if (stream_ids.length === 0) {
        make_archive_folder_request();
        return;
    }

    function on_success(): void {
        successful_requests = successful_requests + 1;

        if (successful_requests === stream_ids.length) {
            // Make request to archive folder only after all channels
            // are removed from the folder.
            make_archive_folder_request();
        }
    }

    function on_error(xhr: JQuery.jqXHR): void {
        ui_report.error(
            $t_html({
                defaultMessage: "Failed removing one or more channels from the folder",
            }),
            xhr,
            $("#dialog_error"),
        );
        dialog_widget.hide_dialog_spinner();
    }

    for (const stream_id of stream_ids) {
        remove_channel_from_folder(stream_id, on_success, on_error);
    }
}

export function handle_archiving_channel_folder(folder_id: number): void {
    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Delete channel folder?"}),
        html_body: render_confirm_archive_channel_folder(),
        on_click() {
            archive_folder(folder_id);
        },
        close_on_submit: false,
        loading_spinner: true,
    });
}

function format_channel_item_html(stream: StreamSubscription): string {
    return render_stream_list_item({
        name: stream.name,
        stream_id: stream.stream_id,
        stream_color: stream.color,
        invite_only: stream.invite_only,
        is_web_public: stream.is_web_public,
        stream_edit_url: hash_util.channels_settings_edit_url(stream, "general"),
        can_manage_folder: can_user_manage_folder(),
    });
}

function render_channel_list(streams: StreamSubscription[], folder_id: number): void {
    const $container = $("#edit_channel_folder .folder-stream-list");
    $container.empty();
    stream_list_widget_stream_ids = new Set(channel_folders.get_stream_ids_in_folder(folder_id));
    channel_folder_stream_list_widget = ListWidget.create($container, streams, {
        name: `edit-channel-folder-stream-list`,
        get_item: ListWidget.default_get_item,
        modifier_html(item) {
            return format_channel_item_html(item);
        },
        filter: {
            $element: $("#edit_channel_folder .stream-list-container .stream-search"),
            predicate(item, value) {
                return item?.name.toLocaleLowerCase().includes(value);
            },
        },
        $simplebar_container: $("#edit_channel_folder .modal__content"),
    });

    $container.on("click", ".remove-button", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const $remove_button = $(e.currentTarget).closest(".remove-button");
        buttons.show_button_loading_indicator($remove_button);
        const stream_id = Number.parseInt(
            $remove_button.closest(".stream-list-item").attr("data-stream-id")!,
            10,
        );

        function on_success(): void {
            banners.open_and_close(
                {
                    intent: "success",
                    label: $t_html({
                        defaultMessage: "Channel removed!",
                    }),
                    buttons: [],
                    close_button: false,
                },
                $("#channel_folder_banner"),
                1200,
            );
        }

        function on_error(xhr: JQuery.jqXHR): void {
            const error_message = channel.xhr_error_message(
                $t_html({
                    defaultMessage: "Failed removing channel from the folder",
                }),
                xhr,
            );
            banners.open_and_close(
                {
                    intent: "danger",
                    label: error_message,
                    buttons: [],
                    close_button: false,
                },
                $("#channel_folder_banner"),
                1200,
            );
            buttons.hide_button_loading_indicator($remove_button);
        }

        remove_channel_from_folder(stream_id, on_success, on_error);
    });
}

function get_edit_modal_folder_id_if_open(): number | undefined {
    const $edit_folder_modal = $("#edit_channel_folder");

    if (!modals.any_active() || $edit_folder_modal.length === 0) {
        return undefined;
    }

    return Number($edit_folder_modal.find(".stream-list-container").attr("data-folder-id"));
}

function get_channel_folder_candidates(folder_id: number): dropdown_widget.Option[] {
    return stream_data
        .get_unsorted_subs()
        .flatMap((stream) =>
            stream.folder_id !== folder_id
                ? [
                      {
                          name: stream.name,
                          unique_id: stream.stream_id,
                          stream,
                      },
                  ]
                : [],
        )
        .toSorted(compare_by_name);
}

function get_channel_folder_candidates_for_dropdown(): dropdown_widget.Option[] {
    const folder_id = get_edit_modal_folder_id_if_open();
    assert(folder_id !== undefined);
    return get_channel_folder_candidates(folder_id);
}

function channel_dropdown_item_click_callback(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
): void {
    dropdown.hide();
    event.preventDefault();
    event.stopPropagation();
    assert(add_channel_folder_widget !== undefined);
    add_channel_folder_widget.render();
    $("#edit_channel_folder .add-channel-button").prop("disabled", false);
}

function reset_add_channel_widget(): void {
    $("#edit_channel_folder .add-channel-button").prop("disabled", true);

    $("#add_channel_folder_widget .dropdown_widget_value").text(
        $t({defaultMessage: "Select a channel"}),
    );

    if (add_channel_folder_widget) {
        add_channel_folder_widget.current_value = undefined;
    }
}

function render_add_channel_folder_widget(): void {
    const opts: DropdownWidgetOptions = {
        widget_name: "add_channel_folder",
        get_options: get_channel_folder_candidates_for_dropdown,
        item_click_callback: channel_dropdown_item_click_callback,
        $events_container: $("#edit_channel_folder"),
        unique_id_type: "number",
    };
    add_channel_folder_widget = new dropdown_widget.DropdownWidget(opts);
    add_channel_folder_widget.setup();

    const $add_channel_button = $("#edit_channel_folder .add-channel-button");
    $("#add_channel_folder_widget .dropdown_widget_value").text(
        $t({defaultMessage: "Select a channel"}),
    );

    $add_channel_button.prop("disabled", true);

    $add_channel_button.on("click", (e) => {
        e.preventDefault();
        assert(add_channel_folder_widget !== undefined);
        const stream_id = add_channel_folder_widget.value();
        assert(typeof stream_id === "number");
        const folder_id = get_edit_modal_folder_id_if_open();
        assert(folder_id !== undefined);
        function on_success(): void {
            reset_add_channel_widget();
            banners.open_and_close(
                {
                    intent: "success",
                    label: $t_html({
                        defaultMessage: "Channel added!",
                    }),
                    buttons: [],
                    close_button: false,
                },
                $("#channel_folder_banner"),
                1200,
            );
        }

        function on_error(xhr: JQuery.jqXHR): void {
            const error_message = channel.xhr_error_message(
                $t_html({
                    defaultMessage: "Failed adding channel to the folder",
                }),
                xhr,
            );
            banners.open_and_close(
                {
                    intent: "danger",
                    label: error_message,
                    buttons: [],
                    close_button: false,
                },
                $("#channel_folder_banner"),
                1200,
            );
            dialog_widget.hide_dialog_spinner();
        }

        add_channel_to_folder(stream_id, folder_id, on_success, on_error);
    });
}

export function update_channel_folder_channels_list(
    stream_id: number,
    folder_id: number | null,
): void {
    const current_folder_id = get_edit_modal_folder_id_if_open();

    if (!current_folder_id) {
        return;
    }

    // We need to update the rendered list when either an item in the current list
    // had a folder_id changed or an unrelated channel was set to current folder id.
    const should_update_channel_list =
        Boolean(stream_list_widget_stream_ids?.has(stream_id)) || folder_id === current_folder_id;

    if (should_update_channel_list && channel_folder_stream_list_widget !== undefined) {
        const subs = channel_folders.get_sorted_streams_in_folder(current_folder_id);
        stream_list_widget_stream_ids = new Set(
            channel_folders.get_stream_ids_in_folder(current_folder_id),
        );
        channel_folder_stream_list_widget.replace_list_data(subs);
    }
}

function update_channel_folder(folder_id: number): void {
    const url = "/json/channel_folders/" + folder_id.toString();
    const new_name = $<HTMLInputElement>("input#edit_channel_folder_name").val()!.trim();
    const new_description = $<HTMLTextAreaElement>("textarea#edit_channel_folder_description")
        .val()!
        .trim();
    const data = {
        name: new_name,
        description: new_description,
    };
    const opts = {
        success_continuation() {
            // Update the channel folders data so that
            // the folder dropdown shows updated folder
            // names immediately even if client receives
            // the update event after some delay.
            channel_folders.update_channel_folder(folder_id, "name", new_name);
            channel_folders.update_channel_folder(folder_id, "description", new_description);
        },
    };
    dialog_widget.submit_api_request(channel.patch, url, data, opts);
}

export function handle_editing_channel_folder(folder_id: number): void {
    const folder = channel_folders.get_channel_folder_by_id(folder_id);
    const subs = channel_folders.get_sorted_streams_in_folder(folder_id);
    const can_manage_folder = can_user_manage_folder();

    const html_body = render_edit_channel_folder_modal({
        name: folder.name,
        description: folder.description,
        folder_id,
        max_channel_folder_name_length: realm.max_channel_folder_name_length,
        max_channel_folder_description_length: realm.max_channel_folder_description_length,
        can_manage_folder,
    });

    const html_heading = can_manage_folder
        ? $t_html({defaultMessage: "Manage channel folder"})
        : $t_html({defaultMessage: "Channel folder details"});

    function on_shown(): void {
        if (!can_manage_folder) {
            return;
        }

        $("#edit_channel_folder_name").trigger("focus");
    }

    dialog_widget.launch({
        html_heading,
        html_body,
        id: "edit_channel_folder",
        on_click() {
            if (!can_manage_folder) {
                // We don't show any submit button for non-admin users
                // so we don't want to do anything here and return.
                return;
            }
            update_channel_folder(folder_id);
        },
        loading_spinner: can_manage_folder,
        on_shown,
        on_hidden() {
            stream_list_widget_stream_ids = undefined;
            add_channel_folder_widget = undefined;
        },
        hide_footer: !can_manage_folder,
        update_submit_disabled_state_on_change: can_manage_folder,
        post_render() {
            render_channel_list(subs, folder_id);
            if (can_manage_folder) {
                render_add_channel_folder_widget();
            }
        },
    });
}
