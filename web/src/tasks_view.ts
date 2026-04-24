import $ from "jquery";
import * as channel from "./channel.ts";
import * as blueslip from "./blueslip.ts";
import { $t } from "./i18n.ts";
import * as task_message_store from "./task_message_store.ts";

// Parse a date-only string from an ISO datetime without timezone conversion.
// Using new Date(iso_string).toLocaleDateString() shifts the date back one day
// for users behind UTC, since midnight UTC becomes the previous day locally.
function format_date_string(iso_string: string): string {
    const date_part = iso_string.slice(0, 10); // e.g. "2025-04-25"
    const [year, month, day] = date_part.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString();
}

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
    // Nullable: standalone tasks created via the assignment form have no message
    message_id: number | null;
    stream_id: number | null;
    topic: string | null;
    // Time tracking fields
    total_time_seconds?: number;
    total_time_formatted?: string;
    active_timer?: boolean;
};

type TimeLog = {
    id: number;
    user_email: string;
    start_time: string;
    end_time: string | null;
    duration_seconds: number;
    duration_formatted: string;
    description: string;
    is_active: boolean;
    created_at: string;
};

export class TasksView {
    tasks: Task[] = [];
    loading = false;
    current_filter: "all" | "completed" | "pending" = "all";
    search_query = "";

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
            const filterType = $(e.target).data("filter");
            this.set_filter(filterType);
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
            this.show_delete_confirmation(task_id);
        });

        // Time tracking handlers
        $("#tasks-overlay .task-item").on("click", ".start-timer-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.start_time_tracking(task_id);
        });

        $("#tasks-overlay .task-item").on("click", ".stop-timer-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.stop_time_tracking(task_id);
        });

        $("#tasks-overlay .task-item").on("click", ".time-logs-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.show_time_logs(task_id);
        });
    }

    set_filter(filter: "all" | "completed" | "pending"): void {
        this.current_filter = filter;
        $("#tasks-overlay .filter-tabs button").removeClass("active");
        $(`#tasks-overlay .filter-tabs button[data-filter="${filter}"]`).addClass("active");
        this.render();
    }

    get_filtered_tasks(): Task[] {
        let filtered = this.tasks;

        // Apply search filter
        if (this.search_query) {
            const query = this.search_query.toLowerCase();
            filtered = filtered.filter(task =>
                task.title.toLowerCase().includes(query) ||
                (task.description && task.description.toLowerCase().includes(query)) ||
                (task.creator_email && task.creator_email.toLowerCase().includes(query))
            );
        }

        // Apply status filter
        switch (this.current_filter) {
            case "completed":
                return filtered.filter(task => task.completed);
            case "pending":
                return filtered.filter(task => !task.completed);
            default:
                return filtered;
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

    show_delete_confirmation(task_id: number): void {
        const modalHtml = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 99999; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 30px; border-radius: 8px; max-width: 400px; width: 90%; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h3 style="margin: 0; color: #000; font-size: 20px; font-weight: 600;">${$t({ defaultMessage: "Delete Task" })}</h3>
                        <button onclick="this.closest('[style*=fixed]').remove()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">&times;</button>
                    </div>
                    <p style="margin: 0 0 25px 0; color: #333; line-height: 1.4;">${$t({ defaultMessage: "Are you sure you want to delete this task? This action cannot be undone." })}</p>
                    <div style="display: flex; gap: 12px; justify-content: flex-end;">
                        <button class="cancel-delete-btn" style="background: #6c757d; color: white; border: none; border-radius: 6px; padding: 10px 20px; cursor: pointer; font-size: 14px; font-weight: 500;">${$t({ defaultMessage: "Cancel" })}</button>
                        <button class="confirm-delete-btn" style="background: #dc3545; color: white; border: none; border-radius: 6px; padding: 10px 20px; cursor: pointer; font-size: 14px; font-weight: 500;">${$t({ defaultMessage: "Delete" })}</button>
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        $("#delete-confirmation-modal").remove();

        // Add the modal
        const $modal = $(modalHtml);
        $modal.attr("id", "delete-confirmation-modal");
        $("body").append($modal);

        // Set up event handlers
        $modal.find(".cancel-delete-btn").on("click", () => {
            $modal.remove();
        });

        $modal.find(".confirm-delete-btn").on("click", () => {
            $modal.remove();
            this.delete_task(task_id);
        });
    }

    delete_task(task_id: number): void {
        // This method now just performs the deletion without confirmation
        // Confirmation is handled by show_delete_confirmation

        const task_to_delete = this.tasks.find(t => t.task_id === task_id);

        channel.post({
            url: `/json/tasks/${task_id}/delete`,
            success: () => {
                this.tasks = this.tasks.filter(t => t.task_id !== task_id);

                if (task_to_delete) {
                    const {message_id, title} = task_to_delete;

                    // Update the client-side store
                    if (message_id !== null) {
                        task_message_store.remove_todo_item_task(message_id, title);
                        // remove_message_task is handled inside remove_todo_item_task
                        // but also clean up the message-level entry if nothing remains
                        const still_has_task = this.tasks.some(t => t.message_id === message_id);
                        if (!still_has_task) {
                            task_message_store.remove_message_task(message_id);
                        }
                    }

                    // Revert any visible todo-widget convert buttons for this task
                    $(`.convert-to-task-btn[data-task="${CSS.escape(title)}"]`)
                        .removeClass("task-added")
                        .prop("disabled", false)
                        .text("Add to My Tasks")
                        .css({"background-color": "", "color": ""});
                }

                this.render_modal();
            },
            error: (xhr: JQuery.jqXHR) => {
                blueslip.error("Failed to delete task", {status: xhr.status, responseText: xhr.responseText});
            },
        });
    }

    start_time_tracking(task_id: number): void {
        channel.post({
            url: `/json/tasks/${task_id}/time/start`,
            data: { description: '' },
            success: (response: any) => {
                blueslip.info("Time tracking started", response);
                this.load_tasks(); // Reload to update timer status
            },
            error: (xhr: JQuery.jqXHR) => {
                if (xhr.status === 503) {
                    // Time tracking feature not available yet
                    blueslip.warn("Time tracking feature not available - database migration not applied");
                } else {
                    blueslip.error("Failed to start time tracking", {status: xhr.status, responseText: xhr.responseText});
                }
            },
        });
    }

    stop_time_tracking(task_id: number): void {
        channel.post({
            url: `/json/tasks/${task_id}/time/stop`,
            success: (response: any) => {
                blueslip.info("Time tracking stopped", response);
                this.load_tasks(); // Reload to update timer status
            },
            error: (xhr: JQuery.jqXHR) => {
                if (xhr.status === 503) {
                    // Time tracking feature not available yet
                    blueslip.warn("Time tracking feature not available - database migration not applied");
                } else {
                    blueslip.error("Failed to stop time tracking", {status: xhr.status, responseText: xhr.responseText});
                }
            },
        });
    }

    show_time_logs(task_id: number): void {
        channel.get({
            url: `/json/tasks/${task_id}/time/logs`,
            success: (response: any) => {
                this.render_time_logs_modal(response);
            },
            error: (xhr: JQuery.jqXHR) => {
                if (xhr.status === 503) {
                    // Time tracking feature not available yet
                    blueslip.warn("Time tracking feature not available - database migration not applied");
                } else {
                    blueslip.error("Failed to load time logs", {status: xhr.status, responseText: xhr.responseText});
                }
            },
        });
    }

    render_time_logs_modal(data: any): void {
        const { time_logs, total_time_formatted, active_timer_count } = data;
        
        const modalHtml = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 99999; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 30px; border-radius: 8px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                        <h2 style="margin: 0; color: #000; font-size: 24px; font-weight: 600;">${$t({ defaultMessage: "Time Logs" })}</h2>
                        <button onclick="this.closest('[style*=fixed]').remove()" style="background: none; border: none; font-size: 28px; cursor: pointer; color: #000; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">&times;</button>
                    </div>
                    <div style="margin-bottom: 20px;">
                        <p style="margin: 0; font-size: 16px; color: #333;">
                            <strong>${$t({ defaultMessage: "Total time tracked:" })}</strong> ${total_time_formatted}
                            ${active_timer_count > 0 ? `<span style="color: #28a745; margin-left: 10px;">(${active_timer_count} ${$t({ defaultMessage: "active timer" })})</span>` : ''}
                        </p>
                    </div>
                    <div class="time-logs-list">
                        ${time_logs.length === 0 ? 
                            '<div style="text-align: center; padding: 40px; color: #666; font-size: 16px;">No time logs found</div>' :
                            time_logs.map((log: TimeLog) => `
                                <div style="padding: 15px; border: 1px solid #eee; border-radius: 6px; margin-bottom: 10px; background: #fafafa;">
                                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                                        <div>
                                            <strong>${log.user_email}</strong>
                                            ${log.is_active ? '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 8px;">Active</span>' : ''}
                                        </div>
                                        <div style="text-align: right;">
                                            <div style="font-weight: 600; color: #007bff;">${log.duration_formatted}</div>
                                            <div style="font-size: 12px; color: #999;">
                                                ${new Date(log.start_time).toLocaleString()} 
                                                ${log.end_time ? `- ${new Date(log.end_time).toLocaleString()}` : ''}
                                            </div>
                                        </div>
                                    </div>
                                    ${log.description ? `<div style="color: #666; font-size: 14px; margin-top: 8px;">${log.description}</div>` : ''}
                                </div>
                            `).join('')
                        }
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        $("#time-logs-modal").remove();

        // Add the modal
        const $modal = $(modalHtml);
        $modal.attr("id", "time-logs-modal");
        $("body").append($modal);
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
        const due_date_str = task.due_date ? format_date_string(task.due_date) : null;
        const created_date_str = new Date(task.created_at).toLocaleDateString();

        // Build a navigation link to the originating message (only for channel tasks)
        let message_link_html = "";
        if (task.stream_id && task.topic && task.message_id) {
            const href = `#narrow/channel/${task.stream_id}/topic/${encodeURIComponent(task.topic)}/near/${task.message_id}`;
            message_link_html = `<a href="${href}" class="task-message-link" style="color: #007bff; text-decoration: none; font-weight: 500;">View Message</a>`;
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
                        ${message_link_html}
                    </div>
                    ${task.description ? `<div class="task-description" style="color: #333; font-size: 14px; line-height: 1.4; margin-top: 8px;">${task.description}</div>` : ""}
                    <div class="task-details" style="margin-top: 8px; font-size: 12px; color: #999;">
                        ${task.completed ? '<span class="task-completed" style="margin-left: 15px; color: #28a745;">Completed</span>' : '<span class="task-pending" style="margin-left: 15px; color: #ffc107;">Pending</span>'}
                        ${task.total_time_formatted ? `<span class="task-time" style="margin-left: 15px; color: #007bff;">Time: ${task.total_time_formatted}</span>` : ''}
                        ${task.active_timer ? '<span class="active-timer" style="margin-left: 15px; color: #28a745; font-weight: 500;">Timer Active</span>' : ''}
                    </div>
                </div>
                <div class="task-actions" style="display: flex; flex-direction: column; gap: 4px;">
                    ${task.active_timer ? 
                        `<button class="stop-timer-btn" title="Stop timer" style="background: #ffc107; color: #000; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 11px;">Stop</button>` :
                        `<button class="start-timer-btn" title="Start timer" style="background: #28a745; color: white; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 11px;">Start</button>`
                    }
                    <button class="time-logs-btn" title="View time logs" style="background: #007bff; color: white; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 11px;">Logs</button>
                    <button class="delete-task-btn" title="Delete task" style="background: #dc3545; color: white; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 12px;">×</button>
                </div>
            </div>
        `;
    }

    show_time_stats(): void {
        channel.get({
            url: "/json/users/me/time/stats",
            success: (response: any) => {
                this.render_time_stats_modal(response);
            },
            error: (xhr: JQuery.jqXHR) => {
                if (xhr.status === 503) {
                    // Time tracking feature not available yet
                    blueslip.warn("Time tracking feature not available - database migration not applied");
                } else {
                    blueslip.error("Failed to load time statistics", {status: xhr.status, responseText: xhr.responseText});
                }
            },
        });
    }

    render_time_stats_modal(data: any): void {
        const { 
            total_time_formatted, 
            completed_sessions, 
            active_sessions, 
            recent_week_formatted,
            task_breakdown 
        } = data;
        
        const modalHtml = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 99999; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 30px; border-radius: 8px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                        <h2 style="margin: 0; color: #000; font-size: 24px; font-weight: 600;">${$t({ defaultMessage: "Time Tracking Statistics" })}</h2>
                        <button onclick="this.closest('[style*=fixed]').remove()" style="background: none; border: none; font-size: 28px; cursor: pointer; color: #000; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">&times;</button>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
                        <div style="text-align: center; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #f8f9fa;">
                            <div style="font-size: 24px; font-weight: bold; color: #007bff; margin-bottom: 5px;">${total_time_formatted}</div>
                            <div style="color: #666; font-size: 14px;">${$t({ defaultMessage: "Total Time Tracked" })}</div>
                        </div>
                        <div style="text-align: center; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #f8f9fa;">
                            <div style="font-size: 24px; font-weight: bold; color: #28a745; margin-bottom: 5px;">${completed_sessions}</div>
                            <div style="color: #666; font-size: 14px;">${$t({ defaultMessage: "Completed Sessions" })}</div>
                        </div>
                        <div style="text-align: center; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #f8f9fa;">
                            <div style="font-size: 24px; font-weight: bold; color: #ffc107; margin-bottom: 5px;">${active_sessions}</div>
                            <div style="color: #666; font-size: 14px;">${$t({ defaultMessage: "Active Timers" })}</div>
                        </div>
                        <div style="text-align: center; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #f8f9fa;">
                            <div style="font-size: 24px; font-weight: bold; color: #17a2b8; margin-bottom: 5px;">${recent_week_formatted}</div>
                            <div style="color: #666; font-size: 14px;">${$t({ defaultMessage: "Last 7 Days" })}</div>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <h3 style="margin: 0 0 15px 0; color: #333; font-size: 18px;">${$t({ defaultMessage: "Top Tasks by Time" })}</h3>
                        ${task_breakdown.length === 0 ? 
                            '<div style="text-align: center; padding: 40px; color: #666; font-size: 16px;">No tasks with time tracking data</div>' :
                            task_breakdown.map((task: any, index: number) => `
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; border: 1px solid #eee; border-radius: 6px; margin-bottom: 8px; background: #fafafa;">
                                    <div style="display: flex; align-items: center; gap: 10px;">
                                        <span style="background: #007bff; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold;">${index + 1}</span>
                                        <div>
                                            <div style="font-weight: 600; color: #333;">${task.task_title}</div>
                                            <div style="font-size: 12px; color: #999;">${task.sessions} ${$t({ defaultMessage: "sessions" })}</div>
                                        </div>
                                    </div>
                                    <div style="text-align: right;">
                                        <div style="font-weight: 600; color: #007bff;">${task.total_formatted}</div>
                                    </div>
                                </div>
                            `).join('')
                        }
                    </div>
                </div>
            </div>
        `;

        // Remove any existing modal
        $("#time-stats-modal").remove();

        // Add the modal
        const $modal = $(modalHtml);
        $modal.attr("id", "time-stats-modal");
        $("body").append($modal);
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
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <button class="time-stats-btn" style="background: #007bff; color: white; border: none; border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 14px; font-weight: 500;">${$t({ defaultMessage: "Time Stats" })}</button>
                            <button onclick="this.closest('[style*=fixed]').remove()" style="background: none; border: none; font-size: 28px; cursor: pointer; color: #000; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">&times;</button>
                        </div>
                    </div>
                    <div style="margin-bottom: 16px;">
                        <input type="text" class="task-search-input" placeholder="${$t({ defaultMessage: "Search tasks..." })}" value="${this.search_query}" style="width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; background: #f8f9fa; color: #000; outline: none;" />
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
                    `<div style="text-align: center; padding: 40px; color: #666; font-size: 16px;">${this.search_query ? $t({ defaultMessage: "No tasks match your search" }) : $t({ defaultMessage: "No tasks found" })}</div>` :
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
            this.show_delete_confirmation(task_id);
        });

        // Time tracking handlers for modal
        $("#tasks-modal .task-item").on("click", ".start-timer-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.start_time_tracking(task_id);
        });

        $("#tasks-modal .task-item").on("click", ".stop-timer-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.stop_time_tracking(task_id);
        });

        $("#tasks-modal .task-item").on("click", ".time-logs-btn", (e) => {
            e.stopPropagation();
            const $task_item = $(e.target).closest(".task-item");
            const task_id = $task_item.data("task-id");
            this.show_time_logs(task_id);
        });

        // Time stats button handler
        $("#tasks-modal .time-stats-btn").on("click", (e) => {
            e.stopPropagation();
            this.show_time_stats();
        });

        // Search input handler
        $("#tasks-modal .task-search-input").on("input", (e) => {
            this.search_query = $(e.target).val() as string;
            this.render_modal();
            // Re-focus the search input and restore cursor position
            const inputEl = $("#tasks-modal .task-search-input")[0] as HTMLInputElement | undefined;
            if (inputEl) {
                const len = this.search_query.length;
                inputEl.setSelectionRange(len, len);
                inputEl.focus();
            }
        });
    }

    hide(): void {
        $("#tasks-overlay").hide();
    }
}

// Initialize when DOM is ready
$(() => {
    // Pre-load which messages already have tasks so button states are
    // correct before the user opens the My Tasks panel.
    task_message_store.initialize();

    // Use event delegation - works even if button is created later
    $(document).on("click", "#tasks-toggle-button", () => {
        tasks_view.show();
    });
});

const tasks_view = new TasksView();
export { tasks_view };