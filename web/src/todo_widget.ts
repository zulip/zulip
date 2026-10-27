import {$} from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_message_hidden_dialog from "../templates/message_hidden_dialog.hbs";
import render_widgets_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_widgets_todo_widget_task from "../templates/widgets/todo_widget_task.hbs";
import render_widgets_todo_widget_task_label from "../templates/widgets/todo_widget_task_label.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import {page_params} from "./page_params.ts";
import type {TodoWidgetOutboundData} from "./todo_data.ts";
import {TaskData} from "./todo_data.ts";
import type {Event} from "./widget_data.ts";
import type {AnyWidgetData, WidgetData} from "./widget_schema.ts";

export function activate({any_data, message}: {any_data: AnyWidgetData; message: Message}): {
    inbound_events_handler: (events: Event[]) => void;
    widget_data: WidgetData;
} {
    assert(any_data.widget_type === "todo");
    const {task_list_title = "", tasks = []} = any_data.extra_data ?? {};
    const task_data = new TaskData({
        message_sender_id: message.sender_id,
        task_list_title,
        tasks,
        report_error_function: blueslip.warn,
    });
    const widget_data = {
        widget_type: any_data.widget_type,
        data: task_data,
    };

    const handle_events = function (events: Event[]): void {
        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }
    };

    return {inbound_events_handler: handle_events, widget_data};
}

export function render({
    $elem,
    callback,
    message,
    widget_data,
    rerender,
}: {
    $elem: JQuery;
    callback: (data: TodoWidgetOutboundData, on_error?: (xhr: JQuery.jqXHR) => void) => void;
    message: Message;
    widget_data: WidgetData;
    rerender: boolean;
}): void {
    assert(widget_data.widget_type === "todo");
    const task_data = widget_data.data;
    const is_my_task_list = task_data.is_my_task_list();
    const message_container = message_lists.current?.view.message_containers.get(message.id);

    function update_edit_controls(): void {
        const has_title =
            $elem.find<HTMLInputElement>("input.todo-task-list-title").val()?.trim() !== "";
        $elem.find("button.todo-task-list-title-check").toggle(has_title);
    }

    function render_task_list_title(): void {
        const task_list_title = task_data.get_task_list_title();
        const input_mode = task_data.get_input_mode();
        const can_edit = is_my_task_list && !input_mode;

        $elem.find(".todo-task-list-title-header").toggle(!input_mode);
        $elem.find(".todo-task-list-title-header").text(task_list_title);
        $elem.find(".todo-edit-task-list-title").toggle(can_edit);
        update_edit_controls();

        $elem.find(".todo-task-list-title-bar").toggle(input_mode);
    }

    function start_editing(): void {
        task_data.set_input_mode();

        const task_list_title = task_data.get_task_list_title();
        $elem.find("input.todo-task-list-title").val(task_list_title);
        render_task_list_title();
        $elem.find("input.todo-task-list-title").trigger("focus");
    }

    function abort_edit(): void {
        task_data.clear_input_mode();
        render_task_list_title();
    }

    function submit_task_list_title(): void {
        const $task_list_title_input = $elem.find<HTMLInputElement>("input.todo-task-list-title");
        let new_task_list_title = $task_list_title_input.val()?.trim() ?? "";
        const old_task_list_title = task_data.get_task_list_title();

        // We should disable the button for blank task list title,
        // so this is just defensive code.
        if (new_task_list_title.trim() === "") {
            new_task_list_title = old_task_list_title;
        }

        // Optimistically set the task list title locally.
        task_data.set_task_list_title(new_task_list_title);
        render_task_list_title();

        // If there were no actual edits, we can exit now.
        if (new_task_list_title === old_task_list_title) {
            return;
        }

        // Broadcast the new task list title to our peers.
        const data = task_data.handle.new_task_list_title.outbound(new_task_list_title);
        if (data) {
            callback(data);
        }
    }

    function add_task(): void {
        $elem.find(".add-task-bar .widget-error").text("");
        const task =
            $elem.find<HTMLInputElement>(".add-task-bar input.add-task").val()?.trim() ?? "";
        const desc =
            $elem.find<HTMLInputElement>(".add-task-bar input.add-desc").val()?.trim() ?? "";
        if (task === "") {
            return;
        }

        $elem.find(".add-task-bar input.add-task").val("").trigger("focus");
        $elem.find(".add-task-bar input.add-desc").val("");

        // This case should not generally occur.
        const task_exists = task_data.name_in_use(task);
        if (task_exists) {
            $elem
                .find(".add-task-bar .widget-error")
                .text($t({defaultMessage: "Task already exists"}));
            return;
        }

        const data = task_data.handle.new_task.outbound(task, desc);
        if (data) {
            callback(data);
        }
    }

    function abort_edit_item($task_list_item: JQuery): void {
        task_data.remove_editing_item(get_task_key($task_list_item));
        update_task_edit_controls($task_list_item);
    }

    function submit_task_list_item($task_list_item: JQuery): void {
        const key = get_task_key($task_list_item);
        const $edit_bar = $task_list_item.find(".todo-task-edit-bar");
        const new_task = $edit_bar.find<HTMLInputElement>("input.add-task").val()?.trim() ?? "";
        const new_desc = $edit_bar.find<HTMLInputElement>("input.add-desc").val()?.trim() ?? "";

        // The save button is hidden while the task name is blank, so
        // this only guards against pressing Enter.
        if (new_task === "") {
            return;
        }
        const old_task_list_item = task_data.get_task_item(key);

        if (!old_task_list_item) {
            blueslip.warn("Do we have legacy data? unknown key for tasks: " + key);
            abort_edit_item($task_list_item);
            return;
        }
        if (new_task === old_task_list_item.task && new_desc === old_task_list_item.desc) {
            abort_edit_item($task_list_item);
            return;
        }

        // Reject duplicate names before entering the loading state so that the
        // spinner never flashes on and immediately off for a no-op validation
        // failure.
        const data = task_data.handle.edit_task.outbound(new_task, new_desc, key);
        if (!data) {
            task_data.set_edit_error(key, $t_html({defaultMessage: "Task already exists"}));
            update_task_edit_controls($task_list_item);
            return;
        }

        // Record exactly what we're sending, so that we recognize the
        // server's broadcast of this edit when it comes back to us.
        $edit_bar.find("input.add-task").val(new_task);
        $edit_bar.find("input.add-desc").val(new_desc);
        task_data.set_editing_item(key, {task: new_task, desc: new_desc});

        // Saving disables the edit bar's buttons. If one of them has
        // focus, move it to the task input, which stays focusable while
        // read-only, so that focus doesn't fall to the page.
        if ($edit_bar.find(".todo-task-edit-buttons-wrapper :focus").length > 0) {
            $edit_bar.find("input.add-task").trigger("focus");
        }

        task_data.start_submitting_edit(key);
        update_task_edit_controls($task_list_item);

        // The edit bar closes when the server broadcasts this edit back
        // to us, in TaskData's edit_task inbound handler, so we only
        // need to handle the request failing here.
        callback(data, (xhr) => {
            // If the edit reached the server even though its response
            // didn't reach us, its broadcast may have closed the edit
            // bar already.
            if (!task_data.is_submitting_edit(key)) {
                return;
            }
            task_data.stop_submitting_edit(
                key,
                channel.xhr_error_message($t_html({defaultMessage: "Failed to save task"}), xhr),
            );
            rerender_in_current_view();
        });
    }

    // Asynchronous callbacks may run after the message has been
    // rendered into a new element (e.g., after a narrow change), so
    // they rerender the widget wherever it's currently displayed,
    // rather than updating the possibly stale $elem.
    function rerender_in_current_view(): void {
        const $current_elem = message_lists.current?.get_row(message.id).find(".widget-content");
        if ($current_elem !== undefined && $current_elem.length > 0) {
            render({$elem: $current_elem, callback, message, widget_data, rerender: true});
        }
    }

    function get_task_key($task_list_item: JQuery): string {
        const key = $task_list_item.attr("data-key");
        assert(key !== undefined);
        return key;
    }

    function build_widget(): void {
        const html = render_widgets_todo_widget();
        $elem.html(html);

        // This throttling ensures that the function runs only after the user stops typing.
        const throttled_update_add_task_button = _.throttle(update_add_task_button, 300);
        $elem.find(".add-task-bar input.add-task").on("keyup", (e) => {
            e.stopPropagation();
            throttled_update_add_task_button();
        });

        $elem.find("input.todo-task-list-title").on("keyup", (e) => {
            e.stopPropagation();
            update_edit_controls();
        });

        $elem.find("input.todo-task-list-title").on("keydown", (e) => {
            e.stopPropagation();

            if (e.key === "Enter") {
                submit_task_list_title();
                return;
            }

            if (e.key === "Escape") {
                abort_edit();
                return;
            }
        });

        $elem.find(".todo-edit-task-list-title").on("click", (e) => {
            e.stopPropagation();
            start_editing();
        });

        $elem.find("button.todo-task-list-title-check").on("click", (e) => {
            e.stopPropagation();
            submit_task_list_title();
        });

        $elem.find("button.todo-task-list-title-remove").on("click", (e) => {
            e.stopPropagation();
            abort_edit();
        });

        $elem.find("button.add-task").on("click", (e) => {
            e.stopPropagation();
            add_task();
        });

        $elem
            .find(".add-task-bar input.add-task, .add-task-bar input.add-desc")
            .on("keydown", (e) => {
                if (e.key === "Enter") {
                    e.stopPropagation();
                    e.preventDefault();
                    add_task();
                }
            });

        $elem.find("ul.todo-widget").on("click", "input.task", (e) => {
            e.stopPropagation();

            if (page_params.is_spectator) {
                // Logically, spectators should not be able to toggle
                // TODO checkboxes. However, the browser changes the
                // checkbox's state before calling handlers like this,
                // so we need to just toggle the checkbox back to its
                // previous state.
                $(e.target).prop("checked", !$(e.target).is(":checked"));
                $(e.target).trigger("blur");
                return;
            }
            const key = get_task_key($(e.target).closest(".todo-task-item"));
            const data = task_data.handle.strike.outbound(key);
            callback(data);
        });

        $elem
            .find("ul.todo-widget")
            .on(
                "keydown",
                ".todo-task-edit-bar input.add-task, .todo-task-edit-bar input.add-desc",
                (e) => {
                    e.stopPropagation();
                    const $task_list_item = $(e.target).closest(".todo-task-item");
                    // While an edit is being saved, its inputs are read-only,
                    // and it can't be resubmitted or cancelled.
                    if (task_data.is_submitting_edit(get_task_key($task_list_item))) {
                        return;
                    }
                    if (keydown_util.is_enter_event(e)) {
                        e.preventDefault();
                        submit_task_list_item($task_list_item);
                        return;
                    }
                    if (e.key === "Escape") {
                        abort_edit_item($task_list_item);
                    }
                },
            );

        $elem.find("ul.todo-widget").on("click", ".todo-edit-task-icon", (e) => {
            e.stopPropagation();
            const $task_list_item = $(e.target).closest(".todo-task-item");
            start_editing_item($task_list_item);
            $task_list_item.find(".todo-task-edit-bar input.add-task").trigger("focus");
        });

        $elem
            .find("ul.todo-widget")
            .on("click", ".todo-task-edit-bar .todo-task-edit-check", (e) => {
                e.stopPropagation();
                submit_task_list_item($(e.target).closest(".todo-task-item"));
            });

        $elem
            .find("ul.todo-widget")
            .on("click", ".todo-task-edit-bar .todo-task-edit-cancel", (e) => {
                e.stopPropagation();
                abort_edit_item($(e.target).closest(".todo-task-item"));
            });

        // Persist the in-progress edit so it survives a rerender that
        // rebuilds the list. We store the raw value and only trim when
        // submitting, so leading/trailing spaces a user is typing are
        // not stripped mid-edit.
        $elem
            .find("ul.todo-widget")
            .on(
                "input",
                ".todo-task-edit-bar input.add-task, .todo-task-edit-bar input.add-desc",
                (e) => {
                    const $task_list_item = $(e.target).closest(".todo-task-item");
                    const $edit_bar = $task_list_item.find(".todo-task-edit-bar");
                    task_data.set_editing_item(get_task_key($task_list_item), {
                        task: $edit_bar.find<HTMLInputElement>("input.add-task").val() ?? "",
                        desc: $edit_bar.find<HTMLInputElement>("input.add-desc").val() ?? "",
                    });
                    update_task_edit_controls($task_list_item);
                },
            );
    }

    function update_add_task_button(): void {
        const task =
            $elem.find<HTMLInputElement>(".add-task-bar input.add-task").val()?.trim() ?? "";
        const task_exists = task_data.name_in_use(task);
        const $add_task_wrapper = $elem.find(".add-task-wrapper");
        const $add_task_button = $elem.find("button.add-task");

        if (task === "") {
            $add_task_wrapper.attr(
                "data-tippy-content",
                $t({defaultMessage: "Name the task before adding."}),
            );
            $add_task_button.prop("disabled", true);
        } else if (task_exists) {
            $add_task_wrapper.attr(
                "data-tippy-content",
                $t({defaultMessage: "Cannot add duplicate task."}),
            );
            $add_task_button.prop("disabled", true);
        } else {
            $add_task_wrapper.removeAttr("data-tippy-content");
            $add_task_button.prop("disabled", false);
        }
    }

    // Updates a task's edit button and edit bar to match its edit state.
    function update_task_edit_controls($task_list_item: JQuery): void {
        const edit_state = task_data.get_editing_items().get(get_task_key($task_list_item));
        const input_mode = edit_state !== undefined;
        const submitting = edit_state?.submitting ?? false;
        const $edit_bar = $task_list_item.find(".todo-task-edit-bar");
        const active_element = document.activeElement;
        const closing_with_focus =
            !input_mode && active_element !== null && $edit_bar.has(active_element).length > 0;

        $task_list_item.find(".checkbox").toggle(!input_mode);
        $task_list_item.find(".todo-edit-task-icon").toggle(!input_mode);
        $edit_bar.toggle(input_mode);
        if (closing_with_focus) {
            // Rather than let focus fall to the page from the now-hidden
            // edit bar, return it to the button that opened the edit bar.
            $task_list_item.find(".todo-edit-task-icon").trigger("focus");
        }

        // While saving, show a spinner and lock the edit bar. The inputs
        // are read-only rather than disabled, so that they keep focus.
        $edit_bar.find("input.add-task, input.add-desc").prop("readOnly", submitting);
        $edit_bar.find(".todo-task-edit-cancel").prop("disabled", submitting);
        $edit_bar.find(".todo-task-edit-check").prop("disabled", submitting);
        $edit_bar.find(".todo-task-check").toggle(!submitting);
        $edit_bar.find(".todo-task-spinner").toggle(submitting);

        // Like the task list title's, the save button is hidden while
        // the task name is blank.
        $edit_bar.find(".todo-task-edit-check").toggle(edit_state?.task.trim() !== "");
        const error_html = edit_state?.error_html ?? "";
        $task_list_item.find(".widget-error").html(error_html);
    }

    function start_editing_item($task_list_item: JQuery): void {
        const key = get_task_key($task_list_item);
        const task_item = task_data.get_task_item(key);
        if (task_item === undefined) {
            return;
        }
        $task_list_item.find(".todo-task-edit-bar input.add-task").val(task_item.task);
        $task_list_item.find(".todo-task-edit-bar input.add-desc").val(task_item.desc);

        task_data.set_editing_item(key, {task: task_item.task, desc: task_item.desc});
        update_task_edit_controls($task_list_item);
    }

    function render_results(): void {
        const $task_list = $elem.find("ul.todo-widget");
        const task_list_items_by_key = new Map<string, JQuery>();
        for (const task_list_item of $task_list.children(".todo-task-item")) {
            const $task_list_item = $(task_list_item);
            task_list_items_by_key.set(get_task_key($task_list_item), $task_list_item);
        }
        for (const task of task_data.get_widget_data().all_tasks) {
            let $task_list_item = task_list_items_by_key.get(task.key);
            if ($task_list_item === undefined) {
                $task_list_item = $(render_widgets_todo_widget_task({...task, is_my_task_list}));
                $task_list.append($task_list_item);
                // The task may already be being edited, if the message
                // was rendered somewhere else first.
                const edit_state = task_data.get_editing_items().get(task.key);
                if (edit_state !== undefined) {
                    $task_list_item.find(".todo-task-edit-bar input.add-task").val(edit_state.task);
                    $task_list_item.find(".todo-task-edit-bar input.add-desc").val(edit_state.desc);
                }
            } else {
                $task_list_item.find("input.task").prop("checked", task.completed);
                $task_list_item
                    .find(".todo-task")
                    .replaceWith($(render_widgets_todo_widget_task_label(task)));
            }
            if (is_my_task_list) {
                update_task_edit_controls($task_list_item);
            }
        }
        $elem.find(".add-task-bar .widget-error").text("");

        update_add_task_button();
    }

    if (message_container?.is_hidden) {
        if (!rerender) {
            const html = render_message_hidden_dialog();
            $elem.html(html);
        }
        return;
    }

    if (!rerender) {
        build_widget();
    }

    render_task_list_title();
    render_results();

    return;
}
