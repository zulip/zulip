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

// Captures which edit-bar input is focused and its caret/selection, so
// the state can be restored after a rerender rebuilds the list and
// destroys the original input elements.
type EditInputFocusState = {
    key: string;
    field: "add-task" | "add-desc";
    selection_start: number | null;
    selection_end: number | null;
    selection_direction: "forward" | "backward" | "none" | null;
};

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
    callback: (
        data: TodoWidgetOutboundData,
        on_success?: () => void,
        on_error?: () => void,
    ) => void;
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

    function abort_edit_item(key: string): void {
        task_data.remove_editing_item(key);
        update_task_edit_controls(key);
        // Remove any stale error message.
        get_task_list_item(key).find(".widget-error").text("");
    }

    function submit_task_list_item(key: string): void {
        if (!is_my_task_list) {
            abort_edit_item(key);
            return;
        }
        const $task_list_item = get_task_list_item(key);
        const new_task =
            $task_list_item.find<HTMLInputElement>("input.add-task").val()?.trim() ?? "";
        const new_desc =
            $task_list_item.find<HTMLInputElement>("input.add-desc").val()?.trim() ?? "";

        if (new_task === "") {
            return;
        }
        const old_task_list_item = task_data.get_task_item(key);

        if (!old_task_list_item) {
            blueslip.warn("Do we have legacy data? unknown key for tasks: " + key);
            abort_edit_item(key);
            return;
        }
        if (new_task === old_task_list_item.task && new_desc === old_task_list_item.desc) {
            abort_edit_item(key);
            return;
        }

        // Reject duplicate names before entering the loading state so that the
        // spinner never flashes on and immediately off for a no-op validation
        // failure.
        const data = task_data.handle.edit_task.outbound(new_task, new_desc, key);
        if (!data) {
            $task_list_item.find(".widget-error").text($t({defaultMessage: "Task already exists"}));
            return;
        }

        // Show the loading spinner and disable the edit controls while the
        // server request is in flight.  The inputs, cancel, and submit
        // controls are all disabled, so the edit session cannot be closed
        // or re-submitted until the server responds; the callbacks below
        // can therefore act unconditionally.
        enter_loading_state(key);

        function success_handler(): void {
            exit_loading_state(key);
            abort_edit_item(key);
        }

        function error_handler(): void {
            exit_loading_state(key);
        }

        callback(data, success_handler, error_handler);
    }

    function get_task_list_item(key: string): JQuery {
        return $elem.find(`input.task[data-key="${key}"]`).closest("li");
    }

    function get_task_key_from_event(e: JQuery.TriggeredEvent): string {
        const key = $(e.target).closest("li").find("label.checkbox input.task").attr("data-key");
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

        $elem.find("ul.todo-widget").on("keydown", ".todo-task-edit-bar input", (e) => {
            e.stopPropagation();
            if (e.key === "Enter") {
                e.preventDefault();
                submit_task_list_item(get_task_key_from_event(e));
                return;
            }
            if (e.key === "Escape") {
                abort_edit_item(get_task_key_from_event(e));
            }
        });

        $elem.find("ul.todo-widget").on("click", ".todo-edit-task-icon", (e) => {
            e.stopPropagation();
            const key = get_task_key_from_event(e);
            start_editing_item(key);
            $(e.target).closest("li").find(".todo-task-edit-bar input.add-task").trigger("focus");
        });

        $elem
            .find("ul.todo-widget")
            .on("click", ".todo-task-edit-bar .todo-task-edit-check", (e) => {
                e.stopPropagation();
                submit_task_list_item(get_task_key_from_event(e));
            });

        $elem
            .find("ul.todo-widget")
            .on("click", ".todo-task-edit-bar .todo-task-edit-cancel", (e) => {
                e.stopPropagation();
                abort_edit_item(get_task_key_from_event(e));
            });

        // Persist the in-progress edit so it survives a rerender that
        // rebuilds the list.  We store the raw value and only trim when
        // submitting, so leading/trailing spaces a user is typing are
        // not stripped mid-edit.
        $elem
            .find("ul.todo-widget")
            .on(
                "input",
                ".todo-task-edit-bar input.add-task, .todo-task-edit-bar input.add-desc",
                (e) => {
                    const key = get_task_key_from_event(e);
                    const $task_list_item = get_task_list_item(key);
                    const task =
                        $task_list_item
                            .find<HTMLInputElement>(".todo-task-edit-bar input.add-task")
                            .val() ?? "";
                    const desc =
                        $task_list_item
                            .find<HTMLInputElement>(".todo-task-edit-bar input.add-desc")
                            .val() ?? "";
                    task_data.set_editing_item(key, {task, desc});
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

    function update_task_edit_submit_loading(key: string, is_loading: boolean): void {
        const $edit_item_bar = get_task_list_item(key).find(".todo-task-edit-bar");
        $edit_item_bar.find("input").prop("disabled", is_loading);
        $edit_item_bar.find(".todo-task-edit-cancel").prop("disabled", is_loading);
        $edit_item_bar.find("i.todo-task-check").toggle(!is_loading);
        $edit_item_bar.find("i.todo-task-spinner").toggle(is_loading);
        $edit_item_bar.find(".todo-task-edit-check").prop("disabled", is_loading);
    }

    function enter_loading_state(key: string): void {
        task_data.set_submitting_state(key, true);
        update_task_edit_submit_loading(key, true);
    }

    function exit_loading_state(key: string): void {
        task_data.set_submitting_state(key, false);
        update_task_edit_submit_loading(key, false);
    }

    function update_task_edit_controls(key: string): void {
        const input_mode = task_data.get_editing_items().has(key);
        const $task_list_item = get_task_list_item(key);
        const can_edit = is_my_task_list && !input_mode;
        $task_list_item.find(".checkbox").toggle(!input_mode);
        $task_list_item.find(".todo-task-edit-bar").toggle(input_mode);
        $task_list_item.find(".todo-edit-task-icon").toggle(can_edit);
    }

    function start_editing_item(key: string): void {
        const task_item = task_data.get_task_item(key);
        if (task_item === undefined) {
            return;
        }
        const $task_list_item = get_task_list_item(key);
        $task_list_item.find(".todo-task-edit-bar input.add-task").val(task_item.task);
        $task_list_item.find(".todo-task-edit-bar input.add-desc").val(task_item.desc);

        task_data.set_editing_item(key, {task: task_item.task, desc: task_item.desc});
        update_task_edit_controls(key);
    }

    function render_results(): void {
        const widget_data = task_data.get_widget_data();
        const html = render_widgets_todo_widget_tasks(widget_data);

        // Rebuilding the list below destroys the edit-bar inputs, so
        // capture the focused input and its caret to restore afterward.
        const edit_input_focus_state = get_edit_input_focus_state();

        $elem.find("ul.todo-widget").html(html);
        $elem.find(".add-task-bar .widget-error").text("");
        $elem.find(".todo-task-edit-bar").hide();
        $elem.find(".todo-edit-task-icon").toggle(is_my_task_list);

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

        function restore_todo_item_edit_state(): void {
            for (const [key, {task, desc, submitting}] of task_data.get_editing_items().entries()) {
                const $task_list_item = get_task_list_item(key);
                $task_list_item.find(".todo-task-edit-bar input.add-task").val(task);
                $task_list_item.find(".todo-task-edit-bar input.add-desc").val(desc);
                update_task_edit_controls(key);
                if (submitting) {
                    update_task_edit_submit_loading(key, true);
                }
            }
        }

        function get_edit_input_focus_state(): EditInputFocusState | undefined {
            const $focused_input = $elem.find<HTMLInputElement>(
                ".todo-task-edit-bar input.add-task:focus, .todo-task-edit-bar input.add-desc:focus",
            );
            const input_element = $focused_input[0];
            if (input_element === undefined) {
                return undefined;
            }
            const key = $focused_input
                .closest("li")
                .find("label.checkbox input.task")
                .attr("data-key");
            if (key === undefined) {
                return undefined;
            }
            return {
                key,
                field: $focused_input.hasClass("add-task") ? "add-task" : "add-desc",
                selection_start: input_element.selectionStart,
                selection_end: input_element.selectionEnd,
                selection_direction: input_element.selectionDirection,
            };
        }

        function restore_edit_input_focus(focus_state: EditInputFocusState | undefined): void {
            if (focus_state === undefined) {
                return;
            }
            const $task_list_item = get_task_list_item(focus_state.key);
            const input_element = $task_list_item.find<HTMLInputElement>(
                `.todo-task-edit-bar input.${focus_state.field}`,
            )[0];
            if (input_element === undefined) {
                return;
            }

            // The input's :focus rule animates its border-color and
            // box-shadow. Re-focusing the freshly rebuilt input would
            // replay that animation on every rerender, flashing the
            // border even though, to the user, focus never left.
            // Suppress the transition for this programmatic focus, then
            // restore it for genuine focus changes.
            input_element.style.transition = "none";
            input_element.focus();
            if (focus_state.selection_start !== null && focus_state.selection_end !== null) {
                input_element.setSelectionRange(
                    focus_state.selection_start,
                    focus_state.selection_end,
                    focus_state.selection_direction ?? undefined,
                );
            }
            // Force the browser to reflow the page so that the transition is applied.
            // eslint-disable-next-line @typescript-eslint/no-unused-expressions
            input_element.offsetHeight;
            input_element.style.transition = "";
        }

        restore_todo_item_edit_state();
        restore_edit_input_focus(edit_input_focus_state);
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
