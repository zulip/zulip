/**
 * Client-side store tracking which messages the current user has already
 * added as tasks, keyed by message ID (for the message-actions popover)
 * and by "messageId:title" (for individual todo-widget items).
 *
 * Stores task_id and widget key alongside so tasks can be deleted (toggled
 * off) and the corresponding todo-widget checkbox can be struck without
 * re-querying the DOM.
 *
 * Populated once at startup from GET /json/users/me/tasks, then kept in
 * sync as the user adds or deletes tasks during the session.
 */

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";

// message_id → task_id (the task created from this message via the popover)
const message_tasks = new Map<number, number>();

type TodoItemEntry = {
    task_id: number;
    // widget key (e.g. "0", "1") needed to post a strike submessage
    key: string | undefined;
};

// "messageId:title" → {task_id, key}
const todo_item_tasks = new Map<string, TodoItemEntry>();

export function initialize(): void {
    channel.get({
        url: "/json/users/me/tasks",
        success: (response: any) => {
            for (const task of response.tasks ?? []) {
                const {task_id, message_id, title} = task;
                if (message_id != null) {
                    // Last task wins if multiple tasks reference the same message
                    message_tasks.set(message_id, task_id);
                }
                if (message_id != null && title) {
                    // key is unknown at init time (widget may not be rendered yet)
                    todo_item_tasks.set(`${message_id}:${title}`, {task_id, key: undefined});
                }
            }
        },
        error: (xhr: JQuery.jqXHR) => {
            blueslip.warn("task_message_store: failed to initialize", {status: xhr.status});
        },
    });
}

// --- Message-level (popover) helpers ---

export function message_has_task(message_id: number): boolean {
    return message_tasks.has(message_id);
}

export function get_message_task_id(message_id: number): number | undefined {
    return message_tasks.get(message_id);
}

export function add_message_task(message_id: number, task_id: number): void {
    message_tasks.set(message_id, task_id);
}

export function remove_message_task(message_id: number): void {
    message_tasks.delete(message_id);
}

// --- Todo-widget item helpers ---

export function todo_item_has_task(message_id: number, title: string): boolean {
    return todo_item_tasks.has(`${message_id}:${title}`);
}

export function get_todo_item_task_id(message_id: number, title: string): number | undefined {
    return todo_item_tasks.get(`${message_id}:${title}`)?.task_id;
}

/**
 * Returns the todo-widget key (e.g. "0", "1") for this task entry.
 * The key is only available when the task was added from an active widget
 * session (not from initialization). Returns undefined if unknown.
 */
export function get_todo_item_key(message_id: number, title: string): string | undefined {
    return todo_item_tasks.get(`${message_id}:${title}`)?.key;
}

export function add_todo_item_task(
    message_id: number,
    title: string,
    task_id: number,
    key?: string,
): void {
    todo_item_tasks.set(`${message_id}:${title}`, {task_id, key});
    // Also register at the message level so the popover reflects "already added"
    if (!message_tasks.has(message_id)) {
        message_tasks.set(message_id, task_id);
    }
}

export function remove_todo_item_task(message_id: number, title: string): void {
    todo_item_tasks.delete(`${message_id}:${title}`);
    // Remove message-level entry only when no todo items for this message remain
    const still_has_todo_task = [...todo_item_tasks.keys()].some((k) =>
        k.startsWith(`${message_id}:`),
    );
    if (!still_has_todo_task) {
        message_tasks.delete(message_id);
    }
}
