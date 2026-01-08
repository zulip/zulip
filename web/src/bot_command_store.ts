// Store for bot-registered slash commands
// This provides autocomplete data for the compose box

import * as channel from "./channel.ts";

export type BotCommand = {
    id: number;
    name: string;
    description: string;
    options: Array<{
        name: string;
        type: string;
        description?: string;
        required?: boolean;
        choices?: Array<{name: string; value: string}>;
    }>;
    bot_id: number;
    bot_name: string;
};

// In-memory store of bot commands
let bot_commands: BotCommand[] = [];

export function initialize(commands: BotCommand[]): void {
    bot_commands = commands;
}

export function get_commands(): BotCommand[] {
    return bot_commands;
}

export function get_command_by_name(name: string): BotCommand | undefined {
    return bot_commands.find((cmd) => cmd.name === name);
}

export function add_command(command: BotCommand): void {
    // Remove existing command with same name if present
    bot_commands = bot_commands.filter((cmd) => cmd.name !== command.name);
    bot_commands.push(command);
}

export function remove_command(command_id: number): void {
    bot_commands = bot_commands.filter((cmd) => cmd.id !== command_id);
}

export function remove_command_by_name(name: string): void {
    bot_commands = bot_commands.filter((cmd) => cmd.name !== name);
}

// Get commands matching a prefix (for typeahead)
export function get_matching_commands(prefix: string): BotCommand[] {
    const lower_prefix = prefix.toLowerCase();
    return bot_commands.filter((cmd) => cmd.name.toLowerCase().startsWith(lower_prefix));
}

// Format a command for display in typeahead
export function format_command_for_typeahead(command: BotCommand): string {
    return `/${command.name}`;
}

// Get the description with bot name for typeahead
export function get_command_description(command: BotCommand): string {
    return `${command.description} (${command.bot_name})`;
}

// ============================================
// Autocomplete functionality for command options
// ============================================

export type AutocompleteChoice = {
    value: string;
    label: string;
};

type CacheEntry = {
    choices: AutocompleteChoice[];
    timestamp: number;
};

// Cache for autocomplete results (expires after 5 seconds)
const autocomplete_cache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 5000;

// In-flight requests to avoid duplicate fetches
const pending_requests = new Map<string, Promise<AutocompleteChoice[]>>();

function make_cache_key(
    bot_id: number,
    command_name: string,
    option_name: string,
    partial_value: string,
): string {
    return `${bot_id}:${command_name}:${option_name}:${partial_value}`;
}

function get_cached_choices(cache_key: string): AutocompleteChoice[] | null {
    const entry = autocomplete_cache.get(cache_key);
    if (!entry) {
        return null;
    }
    // Check if cache is still valid
    if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
        autocomplete_cache.delete(cache_key);
        return null;
    }
    return entry.choices;
}

function set_cached_choices(cache_key: string, choices: AutocompleteChoice[]): void {
    autocomplete_cache.set(cache_key, {
        choices,
        timestamp: Date.now(),
    });
}

type AutocompleteResponse = {
    choices: AutocompleteChoice[];
};

/**
 * Fetch autocomplete suggestions for a bot command option.
 *
 * Returns cached results if available, otherwise fetches from the server.
 * Uses a dedupe mechanism to avoid multiple in-flight requests for the same query.
 */
export async function get_option_suggestions(
    bot_id: number,
    command_name: string,
    option_name: string,
    partial_value: string,
    context: Record<string, unknown> = {},
): Promise<AutocompleteChoice[]> {
    const cache_key = make_cache_key(bot_id, command_name, option_name, partial_value);

    // Return cached if available
    const cached = get_cached_choices(cache_key);
    if (cached !== null) {
        return cached;
    }

    // Check if there's already a pending request for this exact query
    const pending = pending_requests.get(cache_key);
    if (pending) {
        return pending;
    }

    // Create the fetch promise
    const fetch_promise = (async (): Promise<AutocompleteChoice[]> => {
        try {
            const response = (await channel.get({
                url: `/json/bot_commands/${bot_id}/autocomplete`,
                data: {
                    command_name,
                    option_name,
                    partial_value,
                    context: JSON.stringify(context),
                },
            })) as AutocompleteResponse;

            const choices = response.choices ?? [];
            set_cached_choices(cache_key, choices);
            return choices;
        } catch {
            // On error, return empty choices but don't cache the failure
            return [];
        } finally {
            // Clean up pending request
            pending_requests.delete(cache_key);
        }
    })();

    // Track the pending request
    pending_requests.set(cache_key, fetch_promise);

    return fetch_promise;
}

/**
 * Get autocomplete suggestions synchronously, returning cached results
 * and triggering a background fetch if cache is stale.
 *
 * This is useful for typeahead which needs synchronous returns.
 */
export function get_option_suggestions_sync(
    bot_id: number,
    command_name: string,
    option_name: string,
    partial_value: string,
    context: Record<string, unknown> = {},
): AutocompleteChoice[] {
    const cache_key = make_cache_key(bot_id, command_name, option_name, partial_value);

    // Return cached if available
    const cached = get_cached_choices(cache_key);
    if (cached !== null) {
        return cached;
    }

    // Trigger background fetch (don't await)
    void get_option_suggestions(bot_id, command_name, option_name, partial_value, context);

    // Return empty for now - typeahead will update when fetch completes
    return [];
}

/**
 * Clear the autocomplete cache (e.g., when context changes significantly)
 */
export function clear_autocomplete_cache(): void {
    autocomplete_cache.clear();
}
