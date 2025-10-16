// Code from message_store that doesn't make sense to write unit tests for.

import $ from "jquery";

export let extract_message_links = (message_content: string): string[] =>
    [...$(message_content).find("a")].map((link) => link.href);

export function rewire_extract_message_links(value: typeof extract_message_links): void {
    extract_message_links = value;
}
