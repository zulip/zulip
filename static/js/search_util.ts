export function get_search_terms(input: string): string[] {
    const search_terms = input
        .toLowerCase()
        .split(",")
        .map((s) => s.trim());
    return search_terms;
}

export function vanilla_match(opts: {val: string; search_terms: string[]}): boolean {
    /*
        This is a pretty vanilla search criteria
        where we see if any of our search terms
        is in our value. When in doubt we should use
        this for all Zulip filters, but we may
        have more complicated use cases in some
        places.

        This is case insensitive.
    */
    const val = opts.val.toLowerCase();
    return opts.search_terms.some((term) => val.includes(term));
}
