import $ from "jquery";
import * as channel from "./channel.ts";
import * as blueslip from "./blueslip.ts";
import { $t } from "./i18n.ts";
import { filter } from "./inbox_util.ts";

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
        this.setup_handlers();
    }

    load_tasks(): void {
        this.loading = true;
        this.render_modal();

        channel.get({
            url: "/json/users/me/tasks",
            success: (response: any) => {
                this.tasks = response.tasks || [];
                this.loading = false;
                this.render_modal();
            },
            error: (xhr: JQuery.jqXHR) => {
                blueslip.error("Failed to load tasks", {status: xhr.status, responseText: xhr.responseText});
                this.loading = false;
                this.render_modal();
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
                this.render_modal();
            },
            error: (xhr: JQuery.jqXHR) => {
                blueslip.error("Failed to update task", {status: xhr.status, responseText: xhr.responseText});
            },
        });
    }

    delete_task(task_id: number): void {
        if (!confirm($t({ defaultMessage: "Are you sure you want to delete this task?" }))) {
            return;
        }

        channel.post({
            url: `/json/tasks/${task_id}/delete`,
            success: () => {
                this.tasks = this.tasks.filter(t => t.task_id !== task_id);
                this.render_modal();
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
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 30px; border-radius: 8px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);">
                <div class="tasks-overlay-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h2 style="margin: 0; color: #333;">${$t({ defaultMessage: "My Tasks" })}</h2>
                    <button class="close-button" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666;">&times;</button>
                </div>
                <div class="tasks-overlay-content">
                    <div class="filter-tabs" style="display: flex; gap: 10px; margin-bottom: 20px;">
                        <button data-filter="all" class="active" style="padding: 8px 16px; border: 1px solid #ddd; background: #f5f5f5; cursor: pointer;">${$t({ defaultMessage: "All" })} (${this.tasks.length})</button>
                        <button data-filter="pending" style="padding: 8px 16px; border: 1px solid #ddd; background: #f5f5f5; cursor: pointer;">${$t({ defaultMessage: "Pending" })} (${pending_count})</button>
                        <button data-filter="completed" style="padding: 8px 16px; border: 1px solid #ddd; background: #f5f5f5; cursor: pointer;">${$t({ defaultMessage: "Completed" })} (${completed_count})</button>
                    </div>
                    <div class="tasks-list">
                        ${this.loading ?
                '<div style="text-align: center; padding: 40px; color: #666;">Loading...</div>' :
                filtered_tasks.map(task => this.render_task_item(task)).join("")
            }
                    </div>
                </div>
            </div>
        `;

        // Remove existing overlay if present
        $("#tasks-overlay").remove();

        // Create new overlay
        const $overlay = $('<div id="tasks-overlay" class="overlay"></div>');
        $overlay.html(html);

        // Add to body and ensure it's properly positioned
        $("body").append($overlay);

        // Force initial styles
        $overlay.css({
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "display": "none"
        });

        this.setup_handlers();
    }

    render_task_item(task: Task): string {
        const completed_class = task.completed ? "completed" : "";
        const checked_attr = task.completed ? "checked" : "";
        const due_date_str = task.due_date ? new Date(task.due_date).toLocaleDateString() : null;
        const created_date_str = new Date(task.created_at).toLocaleDateString();

        // Generate proper message link
        let message_link = "#";
        if (task.stream_id && task.topic) {
            message_link = `#narrow/channel/${task.stream_id}/${encodeURIComponent(task.topic)}/near/${task.message_id}`;
        } else if (task.message_id) {
            // Fallback for DM messages or if stream info is missing
            message_link = `#narrow/dm/near/${task.message_id}`;
        }

        return `
            <div class="task-item ${completed_class}" data-task-id="${task.task_id}" style="display: flex; align-items: flex-start; gap: 12px; padding: 16px; border: 1px solid #eee; border-radius: 8px; margin-bottom: 12px; background: #fafafa;">
                <div class="task-checkbox" style="margin-top: 2px;">
                    <input type="checkbox" class="task-checkbox" ${checked_attr} style="width: 18px; height: 18px; cursor: pointer;"/>
                </div>
                <div class="task-content" style="flex: 1;">
                    <div class="task-title" style="font-size: 16px; font-weight: 600; color: #000; margin-bottom: 8px; ${task.completed ? 'text-decoration: line-through; color: #666;' : ''}">${task.title}</div>
                    <div class="task-meta" style="display: flex; gap: 15px; align-items: center; font-size: 13px; color: #666; margin-bottom: 8px; flex-wrap: wrap;">
                        <span class="task-creator" style="color: #333;">${task.creator_email || 'Unknown'}</span>
                        <span class="task-created" style="color: #999;">Created: ${created_date_str}</span>
                        ${due_date_str ? `<span class="task-due-date" style="color: #007bff; font-weight: 500;">Due: ${due_date_str}</span>` : '<span class="task-due-date" style="color: #999; font-style: italic;">No due date</span>'}
                        <a href="#narrow/stream/${task.message_id}" class="task-message-link" style="color: #007bff; text-decoration: none; font-weight: 500;">View Message</a>
                    </div>
                    ${task.description ? `<div class="task-description" style="color: #333; font-size: 14px; line-height: 1.4; margin-top: 8px;">${task.description}</div>` : ""}
                    <div class="task-details" style="margin-top: 8px; font-size: 12px; color: #999;">
                        ${task.completed ? '<span class="task-completed" style="margin-left: 15px; color: #28a745;">Completed</span>' : '<span class="task-pending" style="margin-left: 15px; color: #ffc107;">Pending</span>'}
                    </div>
                </div>
                <div class="task-actions">
                    <button class="delete-task-btn" title="Delete task" style="background: #dc3545; color: white; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 12px;">×</button>
                </div>
            </div>
        `;
    }

    show(): void {
        // Load tasks first
        this.load_tasks();

        // Then create the modal with current task data
        this.render_modal();
    }

    render_modal(): void {
        const filtered_tasks = this.get_filtered_tasks();
        const completed_count = this.tasks.filter(t => t.completed).length;
        const pending_count = this.tasks.filter(t => !t.completed).length;

        const modalHtml = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 99999; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 30px; border-radius: 8px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                        <h2 style="margin: 0; color: #000; font-size: 24px; font-weight: 600;">${$t({ defaultMessage: "My Tasks" })}</h2>
                        <button onclick="this.closest('[style*=fixed]').remove()" style="background: none; border: none; font-size: 28px; cursor: pointer; color: #000; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">&times;</button>
                    </div>
                    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                        <button data-filter="all" class="filter-btn ${this.current_filter === 'all' ? 'active' : ''}" style="padding: 10px 18px; border: 2px solid #007bff; background: ${this.current_filter === 'all' ? '#007bff' : 'white'}; color: ${this.current_filter === 'all' ? 'white' : '#007bff'}; cursor: pointer; border-radius: 6px; font-weight: 500; font-size: 14px;">${$t({ defaultMessage: "All" })} (${this.tasks.length})</button>
                        <button data-filter="pending" class="filter-btn ${this.current_filter === 'pending' ? 'active' : ''}" style="padding: 10px 18px; border: 2px solid #28a745; background: ${this.current_filter === 'pending' ? '#28a745' : 'white'}; color: ${this.current_filter === 'pending' ? 'white' : '#28a745'}; cursor: pointer; border-radius: 6px; font-weight: 500; font-size: 14px;">${$t({ defaultMessage: "Pending" })} (${pending_count})</button>
                        <button data-filter="completed" class="filter-btn ${this.current_filter === 'completed' ? 'active' : ''}" style="padding: 10px 18px; border: 2px solid #6c757d; background: ${this.current_filter === 'completed' ? '#6c757d' : 'white'}; color: ${this.current_filter === 'completed' ? 'white' : '#6c757d'}; cursor: pointer; border-radius: 6px; font-weight: 500; font-size: 14px;">${$t({ defaultMessage: "Completed" })} (${completed_count})</button>
                    </div>
                    <div class="tasks-list">
                        ${this.loading ?
                '<div style="text-align: center; padding: 40px; color: #000; font-size: 16px;">Loading...</div>' :
                filtered_tasks.length === 0 ?
                    '<div style="text-align: center; padding: 40px; color: #666; font-size: 16px;">No tasks found</div>' :
                    filtered_tasks.map(task => this.render_task_item(task)).join("")
            }
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        $("#tasks-modal").remove();

        // Add the modal
        const $modal = $(modalHtml);
        $modal.attr("id", "tasks-modal");
        $("body").append($modal);

        // Setup event handlers
        this.setup_modal_handlers();

    }

    setup_modal_handlers(): void {
        $("#tasks-modal .filter-btn").on("click", (e) => {
            const filter = $(e.target).data("filter");
            this.set_filter(filter);
            this.render_modal();
        });

        $("#tasks-modal .task-item").on("click", ".task-checkbox", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.toggle_task_completion(task_id);
            this.render_modal();
        });

        $("#tasks-modal .task-item").on("click", ".delete-task-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.delete_task(task_id);
            this.render_modal();
        });
    }

    hide(): void {
        $("#tasks-overlay").hide();
    }
}

// Initialize when DOM is ready
$(() => {
    // Use event delegation - works even if button is created later
    $(document).on("click", "#tasks-toggle-button", () => {
        tasks_view.show();
    });
});

const tasks_view = new TasksView();
export { tasks_view };