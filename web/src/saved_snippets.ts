import * as blueslip from "./blueslip.ts";
import type {Option} from "./dropdown_widget.ts";
import {$t} from "./i18n.ts";
import type {StateData} from "./state_data.ts";
import * as util from "./util.ts";

export type SavedSnippet = {
    id: number;
    title: string;
    content: string;
    date_created: number;
};

export const ADD_SAVED_SNIPPET_OPTION_ID = -1;
let saved_snippets_dict: Map<number, SavedSnippet>;

export function get_saved_snippet_by_id(saved_snippet_id: number): SavedSnippet | undefined {
    const saved_snippet = saved_snippets_dict.get(saved_snippet_id);
    if (saved_snippet === undefined) {
        blueslip.error("Could not find saved snippet", {saved_snippet_id});
        return undefined;
    }
    return saved_snippet;
}

export function add_saved_snippet(saved_snippet: SavedSnippet): void {
    saved_snippets_dict.set(saved_snippet.id, saved_snippet);
}

export function remove_saved_snippet(saved_snippet_id: number): void {
    saved_snippets_dict.delete(saved_snippet_id);
}

export function get_options_for_dropdown_widget(): Option[] {
    const saved_snippets = [...saved_snippets_dict.values()].sort((a, b) =>
        util.strcmp(a.title.toLowerCase(), b.title.toLowerCase()),
    );
    const options = saved_snippets.map((saved_snippet) => ({
        unique_id: saved_snippet.id,
        name: saved_snippet.title,
        description: saved_snippet.content,
        bold_current_selection: true,
        has_delete_icon: true,
    }));

    // Option for creating a new saved snippet.
    options.unshift({
        unique_id: ADD_SAVED_SNIPPET_OPTION_ID,
        name: $t({defaultMessage: "Add a new saved snippet"}),
        description: "",
        bold_current_selection: true,
        has_delete_icon: false,
    });
    return options;
}

export const initialize = (params: StateData["saved_snippets"]): void => {
    saved_snippets_dict = new Map<number, SavedSnippet>(
        params.saved_snippets.map((s) => [s.id, s]),
    );
};
