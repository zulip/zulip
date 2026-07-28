const $ = require("./zjquery.cjs");

// Represents a single element in JQueryMock
export type MockElement = {
    remove: () => void;
    [key: string]: any; 
};

// A typed mock of FakeJQuery in zjquery_element.cts
export type JQueryMock = {
    [index: number]: MockElement;
    length: number;

    find: (selector: string) => JQueryMock;
    text: {
        (): string;
        (content: string): JQueryMock;
    };
    set_find_results: (selector: string, elements: (MockElement | JQueryMock)[]) => void;

    [Symbol.iterator](): Iterator<MockElement>;
};

export type ZJQueryHelpers = {
    create_mock: (name: string) => JQueryMock;
};

// Returns an object of type JQueryMock
function create_mock(name: string): JQueryMock {
    return $.create(name) as unknown as JQueryMock;
}

module.exports = {
    create_mock,
};
