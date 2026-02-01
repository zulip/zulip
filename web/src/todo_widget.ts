import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_message_hidden_dialog from "../templates/message_hidden_dialog.hbs";
import render_widgets_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_widgets_todo_widget_tasks from "../templates/widgets/todo_widget_tasks.hbs";

import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import {page_params} from "./page_params.ts";
import type {TodoWidgetOutboundData} from "./todo_data.ts";
import {TaskData} from "./todo_data.ts";
import type {Event} from "./widget_data.ts";
import type {AnyWidgetData, WidgetData} from "./widget_schema.ts";

export function activate({
    $elem,
    callback,
    any_data,
    message,
}: {
    $elem: JQuery;
    callback: (data: TodoWidgetOutboundData) => void;
    any_data: AnyWidgetData;
    message: Message;
}): {inbound_events_handler: (events: Event[]) => void, widget_data: WidgetData} {
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
    }

    return {inbound_events_handler: render({$elem, callback, message, task_data}), widget_data};
}

export function render({
    $elem,
    callback,
    message,
    task_data,
}: {
    $elem: JQuery;
    callback: (data: TodoWidgetOutboundData) => void;
    message: Message;
    task_data: TaskData;
}): (events: Event[]) => void {
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
        $elem.find(".widget-error").text("");
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
            $elem.find(".widget-error").text($t({defaultMessage: "Task already exists"}));
            return;
        }

        const data = task_data.handle.new_task.outbound(task, desc);
        if (data) {
            callback(data);
        }
    }

    function build_widget(): void {
        const html = render_widgets_todo_widget();
        $elem.html(html);

        // This throttling ensures that the function runs only after the user stops typing.
        const throttled_update_add_task_button = _.throttle(update_add_task_button, 300);
        $elem.find("input.add-task").on("keyup", (e) => {
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

        $elem.find("input.add-task, input.add-desc").on("keydown", (e) => {
            if (e.key === "Enter") {
                e.stopPropagation();
                e.preventDefault();
                add_task();
            }
        });
    }

    function update_add_task_button(): void {
        const task = $elem.find<HTMLInputElement>("input.add-task").val()?.trim() ?? "";
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

    function render_results(): void {
        const widget_data = task_data.get_widget_data();
        const html = render_widgets_todo_widget_tasks(widget_data);
        $elem.find("ul.todo-widget").html(html);
        $elem.find(".widget-error").text("");

        $elem.find("input.task").on("click", (e) => {
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
            const key = $(e.target).attr("data-key");
            assert(key !== undefined);

            const data = task_data.handle.strike.outbound(key);
            callback(data);
        });

        update_add_task_button();
    }

    const handle_events = function (events: Event[]): void {
        // We don't have to handle events now since we go through
        // handle_event loop again when we unmute the message.
        if (message_container?.is_hidden) {
            return;
        }

        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }

        render_task_list_title();
        render_results();
    };

    if (message_container?.is_hidden) {
        const html = render_message_hidden_dialog();
        $elem.html(html);
    } else {
        build_widget();
        render_task_list_title();
        render_results();
    }

    return handle_events;
}
