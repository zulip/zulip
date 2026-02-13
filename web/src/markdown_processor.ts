import type {MarkdownHelpers} from "./markdown.ts";

/**
 * Interface for markdown processors. Both the legacy marked.js processor
 * and the new unified/mdast processor implement this interface, allowing
 * them to be swapped via a dispatch flag during migration.
 */
export type MarkdownProcessor = {
    process: (
        raw_content: string,
        helper_config: MarkdownHelpers,
    ) => {content: string; flags: string[]};
};
