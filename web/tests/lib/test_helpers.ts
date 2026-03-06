import $ from "./zjquery.cjs";

// Interface for the zjquery mock objects to ensure
// consistency across all node tests.
export type JQueryMock = {
    find: (selector: string) => JQueryMock;
    text: (() => string) & ((content: string) => JQueryMock);
    remove: () => void;
    set_find_results: (selector: string, results: unknown) => void;
    entries: () => [number, JQueryMock][];
};

// Factory for creating typed zjquery mock elements.
// Replaces direct calls to $.create() to satisfy strict typing rules.
export function create_mock(name: string): JQueryMock {
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    return $.create(name) as JQueryMock;
}

// Simulates a jQuery collection for testing loops.
export function mock_collection(array: JQueryMock[]): {
    each: (func: (this: JQueryMock, index?: number, elem?: JQueryMock) => void) => void;
} {
    return {
        each(func: (this: JQueryMock, index?: number, elem?: JQueryMock) => void): void {
            for (const [index, $elem] of array.entries()) {
                func.call($elem, index, $elem);
            }
        },
    };
}
