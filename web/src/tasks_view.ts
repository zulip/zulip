import $ from "jquery";
import * as channel from "./channel.ts";
import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";

type Task = {
    task_id: number;
    title: string;
    description: string;
    completed: boolean;
    due_date: string | null;
    created_at: string;
    completed_at: string | null;
    creator_email: string;
    creator_full_name: string;
    message_id: number;
    stream_id: number | null;
    topic: string | null;
};

export class TasksView {
    tasks: Task[] = [];
    loading = false;
    current_filter: "all" | "completed" | "pending" = "all";

    constructor() {
        this.load_tasks();
        this.setup_handlers();
    }

    load_tasks(): void {
        this.loading = true;
        this.render();

        channel.get({
            url: "/json/users/me/tasks",
            success: (response: any) => {
                this.tasks = response.tasks || [];
                this.loading = false;
                this.render();
            },
            error: (xhr: JQuery.jqXHR) => {
                blueslip.error("Failed to load tasks", {status: xhr.status, responseText: xhr.responseText});
                this.loading = false;
                this.render();
            },
        });
    }

    setup_handlers(): void {
        $("#tasks-overlay .close-button").on("click", () => {
            this.hide();
        });

        $("#tasks-overlay .filter-tabs button").on("click", (e) => {
            const filter = $(e.target).data("filter");
            this.set_filter(filter);
        });

        $("#tasks-overlay .task-item").on("click", ".task-checkbox", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.toggle_task_completion(task_id);
        });

        $("#tasks-overlay .task-item").on("click", ".delete-task-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.delete_task(task_id);
        });
    }

    set_filter(filter: "all" | "completed" | "pending"): void {
        this.current_filter = filter;
        $("#tasks-overlay .filter-tabs button").removeClass("active");
        $(`#tasks-overlay .filter-tabs button[data-filter="${filter}"]`).addClass("active");
        this.render();
    }

    get_filtered_tasks(): Task[] {
        switch (this.current_filter) {
            case "completed":
                return this.tasks.filter(task => task.completed);
            case "pending":
                return this.tasks.filter(task => !task.completed);
            default:
                return this.tasks;
        }
    }

    toggle_task_completion(task_id: number): void {
        const task = this.tasks.find(t => t.task_id === task_id);
        if (!task) return;

        const new_completed = !task.completed;
        
        channel.post({
            url: `/json/tasks/${task_id}`,
            data: { completed: new_completed },
            success: () => {
                task.completed = new_completed;
                task.completed_at = new_completed ? new Date().toISOString() : null;
                this.render();
            },
            error: (xhr: JQuery.jqXHR) => {
                blueslip.error("Failed to update task", {status: xhr.status, responseText: xhr.responseText});
            },
        });
    }

    delete_task(task_id: number): void {
        if (!confirm($t({defaultMessage: "Are you sure you want to delete this task?"}))) {
            return;
        }

        channel.del({
            url: `/json/tasks/${task_id}`,
            success: () => {
                this.tasks = this.tasks.filter(t => t.task_id !== task_id);
                this.render();
            },
            error: (xhr: JQuery.jqXHR) => {
                blueslip.error("Failed to delete task", {status: xhr.status, responseText: xhr.responseText});
            },
        });
    }

    render(): void {
        const filtered_tasks = this.get_filtered_tasks();
        const completed_count = this.tasks.filter(t => t.completed).length;
        const pending_count = this.tasks.filter(t => !t.completed).length;

        const html = `
            <div class="tasks-overlay-header">
                <h2>${$t({defaultMessage: "My Tasks"})}</h2>
                <button class="close-button">&times;</button>
            </div>
            <div class="tasks-overlay-content">
                <div class="filter-tabs">
                    <button data-filter="all" class="active">${$t({defaultMessage: "All"})} (${this.tasks.length})</button>
                    <button data-filter="pending">${$t({defaultMessage: "Pending"})} (${pending_count})</button>
                    <button data-filter="completed">${$t({defaultMessage: "Completed"})} (${completed_count})</button>
                </div>
                <div class="tasks-list">
                    ${this.loading ? 
                        '<div class="loading-spinner"></div>' :
                        filtered_tasks.map(task => this.render_task_item(task)).join("")
                    }
                </div>
            </div>
        `;

        if ($("#tasks-overlay").length === 0) {
            $("body").append(`
                <div id="tasks-overlay" class="overlay">
                    ${html}
                </div>
            `);
        } else {
            $("#tasks-overlay").html(html);
        }

        this.setup_handlers();
    }

    render_task_item(task: Task): string {
        const completed_class = task.completed ? "completed" : "";
        const checked_attr = task.completed ? "checked" : "";
        const due_date_str = task.due_date ? new Date(task.due_date).toLocaleDateString() : "";

        // Generate proper message link
        let message_link = "#";
        if (task.stream_id && task.topic) {
            message_link = `#narrow/channel/${task.stream_id}/${encodeURIComponent(task.topic)}/near/${task.message_id}`;
        } else if (task.message_id) {
            // Fallback for DM messages or if stream info is missing
            message_link = `#narrow/dm/near/${task.message_id}`;
        }

        return `
            <div class="task-item ${completed_class}" data-task-id="${task.task_id}">
                <div class="task-checkbox">
                    <input type="checkbox" class="task-checkbox" ${checked_attr}/>
                    <span class="custom-checkbox"></span>
                </div>
                <div class="task-content">
                    <div class="task-title">${task.title}</div>
                    <div class="task-meta">
                        <span class="task-creator">${task.creator_full_name}</span>
                        ${due_date_str ? `<span class="task-due-date">Due: ${due_date_str}</span>` : ""}
                        <a href="${message_link}" class="task-message-link">View Message</a>
                    </div>
                    ${task.description ? `<div class="task-description">${task.description}</div>` : ""}
                </div>
                <div class="task-actions">
                    <button class="delete-task-btn" title="Delete task">×</button>
                </div>
            </div>
        `;
    }

    show(): void {
        $("#tasks-overlay").show();
        this.load_tasks();
    }

    hide(): void {
        $("#tasks-overlay").hide();
    }
}

// Initialize when DOM is ready
$(() => {
    console.log("Tasks view script loaded!");
    $("#tasks-toggle-button").on("click", () => {
        console.log("Tasks button clicked!");
        tasks_view.show();
    });
});

const tasks_view = new TasksView();
