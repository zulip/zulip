// Store for bot-registered slash commands
// This provides autocomplete data for the compose box

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
