import $ from "jquery";

import render_widgets_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_widgets_todo_widget_tasks from "../templates/widgets/todo_widget_tasks.hbs";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";
import {page_params} from "./page_params";
import * as people from "./people";




type TodoData = {
    key: string,
    task: string,
    desc: string,
    completed: boolean
}
type InboundData = {type: string} & Record<string, unknown>

type ActivateOptions = {
    $elem: JQuery,
    callback: (data: InboundData | undefined) => void
}
type TaskMapData = TodoData & {idx: number}

// Any single user should send add a finite number of tasks
// to a todo list. We arbitrarily pick this value.
const MAX_IDX = 1000;


export class TaskData {
    task_map = new Map<string, TaskMapData>();
    my_idx = 1;
    me: number
    handle = {
        new_task: {
            outbound: (task: string, desc: string): InboundData | undefined => {
                this.my_idx += 1;
                const event: InboundData = {
                    type: "new_task",
                    key: this.my_idx.toString(),
                    task,
                    desc,
                    completed: false,
                };

                if (!this.name_in_use(task)) {
                    return event;
                }
                return undefined;
            },
            

            inbound: (sender_id: number, data: InboundData): void => {
                // All messages readers may add tasks.
                // for legacy reasons, the inbound idx is
                // called key in the event
                const idx = Number.parseInt(data.key, 10);
                const task = data.task;
                const desc = data.desc;
                
                if (!Number.isInteger(idx) || idx < 0 || idx > MAX_IDX) {
                    blueslip.warn("todo widget: bad type for inbound task idx");
                    return;
                }

                if (typeof task !== "string") {
                    blueslip.warn("todo widget: bad type for inbound task title");
                    return;
                }

                if (typeof desc !== "string") {
                    blueslip.warn("todo widget: bad type for inbound task desc");
                    return;
                }

                const key = idx + "," + sender_id;
                const completed = data.completed;

                const task_data = {
                    task,
                    desc,
                    idx,
                    key,
                    completed,
                };

                if (!this.name_in_use(task)) {
                    this.task_map.set(key, task_data);
                }

                // I may have added a task from another device.
                if (sender_id === this.me && this.my_idx <= idx) {
                    this.my_idx = idx + 1;
                }
            },
        },

        strike: {
            outbound(key: string) {
                const event = {
                    type: "strike",
                    key,
                };

                return event;
            },

            inbound: (_sender_id: number, data: InboundData) => {
                // All message readers may strike/unstrike todo tasks.
                const key = data.key;
                if (typeof key !== "string") {
                    blueslip.warn("todo widget: bad type for inbound strike key");
                    return;
                }

                const item = this.task_map.get(key);

                if (item === undefined) {
                    blueslip.warn("Do we have legacy data? unknown key for tasks: " + key);
                    return;
                }

                item.completed = !item.completed;
            },
        },
    };


    constructor({current_user_id}: {current_user_id: number}) {
        this.me = current_user_id;
    }

    get_widget_data(): {all_tasks: TodoData[]} {
        const all_tasks = [...this.task_map.values()];

        const widget_data = {
            all_tasks,
        };

        return widget_data;
    }

    name_in_use(name: string): boolean {
        for (const item of this.task_map.values()) {
            if (item.task === name) {
                return true;
            }
        }

        return false;
    }

    
    handle_event(sender_id: number, data: InboundData): void {
        const type = data.type;
        if (type === "new_task" || type === "strike") {
            this.handle[type].inbound(sender_id, data);
        } else {
            blueslip.warn(`todo widget: unknown inbound type: ${type}`);
        }
    }
}

export function activate(opts: ActivateOptions): void {
    const $elem = opts.$elem;
    const callback = opts.callback;

    const task_data = new TaskData({
        current_user_id: people.my_current_user_id(),
    });

    function render(): void {
        const html = render_widgets_todo_widget();
        $elem.html(html);

        $elem.find("button.add-task").on("click", (e: JQuery.ClickEvent) => {
            e.stopPropagation();
            $elem.find(".widget-error").text("");
            const task = $elem.find<HTMLInputElement>("input.add-task").val()!.trim();
            const desc = $elem.find<HTMLInputElement>("input.add-desc").val()!.trim();
            
            
            if (task === "") {
                return;
            }

            $elem.find("input.add-task").val("").trigger("focus");
            $elem.find("input.add-desc").val("");

            const task_exists = task_data.name_in_use(task);
            if (task_exists) {
                $elem.find(".widget-error").text($t({defaultMessage: "Task already exists"}));
                return;
            }

            const data = task_data.handle.new_task.outbound(task, desc);
            callback(data);
        });
    }

    function render_results(): void {
        const widget_data = task_data.get_widget_data();
        const html = render_widgets_todo_widget_tasks(widget_data);
        $elem.find("ul.todo-widget").html(html);
        $elem.find(".widget-error").text("");

        $elem.find("input.task").on("click", (e: JQuery.ClickEvent) => {
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
            const key = $(e.target).attr("data-key")!;

            const data = task_data.handle.strike.outbound(key);
            callback(data);
        });
    }

    $elem.handle_events = function (events) {
        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }

        render_results();
    };

    render();
    render_results();
}
