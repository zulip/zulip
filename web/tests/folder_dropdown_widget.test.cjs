"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const dropdown_widget = mock_esm("../src/dropdown_widget");
const util = mock_esm("../src/util");

let tippy_default_stub = noop;
let tippy_instance;

const tippy_function = (reference, options) => {
    tippy_default_stub(reference, options);
    tippy_instance = {destroy: noop};
    return tippy_instance;
};
tippy_function.setDefaultProps = noop;

mock_esm("tippy.js", {
    default: tippy_function,
});

const channel_folders = zrequire("channel_folders");
const stream_data = zrequire("stream_data");
const folder_dropdown_widget = zrequire("folder_dropdown_widget");

function initialize_folders() {
    const frontend_folder = {
        name: "Frontend",
        description: "Channels for frontend discussions",
        rendered_description: "<p>Channels for frontend discussions</p>",
        creator_id: null,
        date_created: 1596710000,
        id: 1,
        is_archived: false,
        order: 0,
    };
    const backend_folder = {
        name: "Backend",
        description: "Channels for backend discussions",
        rendered_description: "<p>Channels for backend discussions</p>",
        creator_id: null,
        date_created: 1596720000,
        id: 2,
        is_archived: false,
        order: 1,
    };
    channel_folders.initialize({channel_folders: [frontend_folder, backend_folder]});
    return {frontend_folder, backend_folder};
}

function initialize_streams(folders) {
    stream_data.clear_subscriptions();

    const stream_1 = make_stream({
        stream_id: 1,
        name: "Stream 1",
        folder_id: folders.frontend_folder.id,
        subscribed: true,
    });
    const stream_2 = make_stream({
        stream_id: 2,
        name: "Stream 2",
        folder_id: folders.backend_folder.id,
        subscribed: true,
    });
    const stream_3 = make_stream({
        stream_id: 3,
        name: "Stream 3",
        folder_id: null,
        subscribed: true,
    });

    stream_data.add_sub_for_tests(stream_1);
    stream_data.add_sub_for_tests(stream_2);
    stream_data.add_sub_for_tests(stream_3);

    return {stream_1, stream_2, stream_3};
}

run_test("get_folder_filter_dropdown_options - with uncategorized channels", () => {
    const folders = initialize_folders();
    initialize_streams(folders);

    // Test with no current value
    let options = folder_dropdown_widget.get_folder_filter_dropdown_options();

    assert.equal(options.length, 4); // Any folder + Uncategorized + 2 folders

    // Check "Any folder" option (should be first)
    assert.equal(options[0].name, "translated: Any folder");
    assert.equal(
        options[0].unique_id,
        folder_dropdown_widget.FOLDER_FILTERS.ANY_FOLDER_DROPDOWN_OPTION,
    );
    assert.equal(options[0].is_setting_disabled, true);
    assert.equal(options[0].show_disabled_icon, false);
    assert.equal(options[0].show_disabled_option_name, true);
    assert.equal(options[0].bold_current_selection, false);

    // Check "Uncategorized" option (should be second)
    assert.equal(options[1].name, "translated: Uncategorized");
    assert.equal(
        options[1].unique_id,
        folder_dropdown_widget.FOLDER_FILTERS.UNCATEGORIZED_DROPDOWN_OPTION,
    );
    assert.equal(options[1].is_setting_disabled, true);
    assert.equal(options[1].show_disabled_icon, false);
    assert.equal(options[1].show_disabled_option_name, true);
    assert.equal(options[1].bold_current_selection, false);

    // Check folder options
    assert.equal(options[2].name, "Frontend");
    assert.equal(options[2].unique_id, folders.frontend_folder.id);
    assert.equal(options[2].bold_current_selection, false);

    assert.equal(options[3].name, "Backend");
    assert.equal(options[3].unique_id, folders.backend_folder.id);
    assert.equal(options[3].bold_current_selection, false);

    // Test with current value set to a specific folder
    options = folder_dropdown_widget.get_folder_filter_dropdown_options(folders.frontend_folder.id);
    assert.equal(options[0].bold_current_selection, false); // Any folder not selected
    assert.equal(options[1].bold_current_selection, false); // Uncategorized not selected
    assert.equal(options[2].bold_current_selection, true); // Frontend selected
    assert.equal(options[3].bold_current_selection, false); // Backend not selected

    // Test with current value set to "Any folder"
    options = folder_dropdown_widget.get_folder_filter_dropdown_options(
        folder_dropdown_widget.FOLDER_FILTERS.ANY_FOLDER_DROPDOWN_OPTION,
    );
    assert.equal(options[0].bold_current_selection, true); // Any folder selected
    assert.equal(options[1].bold_current_selection, false);
    assert.equal(options[2].bold_current_selection, false);
    assert.equal(options[3].bold_current_selection, false);

    // Test with current value set to "Uncategorized"
    options = folder_dropdown_widget.get_folder_filter_dropdown_options(
        folder_dropdown_widget.FOLDER_FILTERS.UNCATEGORIZED_DROPDOWN_OPTION,
    );
    assert.equal(options[0].bold_current_selection, false);
    assert.equal(options[1].bold_current_selection, true); // Uncategorized selected
    assert.equal(options[2].bold_current_selection, false);
    assert.equal(options[3].bold_current_selection, false);
});

run_test("get_folder_filter_dropdown_options - without uncategorized channels", () => {
    const folders = initialize_folders();
    stream_data.clear_subscriptions();

    // Only add streams with folder_id (no uncategorized streams)
    const stream_1 = make_stream({
        stream_id: 1,
        name: "Stream 1",
        folder_id: folders.frontend_folder.id,
        subscribed: true,
    });
    const stream_2 = make_stream({
        stream_id: 2,
        name: "Stream 2",
        folder_id: folders.backend_folder.id,
        subscribed: true,
    });

    stream_data.add_sub_for_tests(stream_1);
    stream_data.add_sub_for_tests(stream_2);

    const options = folder_dropdown_widget.get_folder_filter_dropdown_options();

    // Should only have 3 options: Any folder + 2 folders (no Uncategorized)
    assert.equal(options.length, 3);
    assert.equal(options[0].name, "translated: Any folder");
    assert.equal(options[1].name, "Frontend");
    assert.equal(options[2].name, "Backend");
});

run_test("get_folder_filter_dropdown_options - empty folders", () => {
    channel_folders.initialize({channel_folders: []});
    stream_data.clear_subscriptions();

    const options = folder_dropdown_widget.get_folder_filter_dropdown_options();

    // Should only have "Any folder" option when there are no folders
    assert.equal(options.length, 1);
    assert.equal(options[0].name, "translated: Any folder");
});

run_test("create_folder_filter_dropdown_widget", () => {
    const folders = initialize_folders();
    initialize_streams(folders);

    const $events_container = $.create("events-container");
    let created_widget_params;

    dropdown_widget.DropdownWidget = function (params) {
        created_widget_params = params;
        return {
            render: noop,
            value: () => -2,
        };
    };

    const widget_name = "test_folder_filter";
    const widget_selector = "#test_folder_filter_widget";
    const item_click_callback = noop;
    const default_id = folder_dropdown_widget.FOLDER_FILTERS.ANY_FOLDER_DROPDOWN_OPTION;

    const widget = folder_dropdown_widget.create_folder_filter_dropdown_widget({
        widget_name,
        widget_selector,
        item_click_callback,
        $events_container,
        default_id,
    });

    assert.ok(widget !== undefined);
    assert.equal(widget.value(), default_id);
    assert.equal(created_widget_params.widget_name, widget_name);
    assert.equal(created_widget_params.widget_selector, widget_selector);
    assert.equal(created_widget_params.item_click_callback, item_click_callback);
    assert.equal(created_widget_params.$events_container, $events_container);
    assert.equal(created_widget_params.unique_id_type, "number");
    assert.equal(created_widget_params.default_id, default_id);
    assert.equal(typeof created_widget_params.get_options, "function");

    // Verify get_options function returns correct data
    const options = created_widget_params.get_options();
    assert.ok(options.length > 0);
    assert.equal(options[0].name, "translated: Any folder");
});

run_test("update_tooltip_for_folder_filter - Any folder", () => {
    initialize_folders();
    let tippy_content;
    let tippy_target;

    const body_stub = {};
    global.document = {body: body_stub};

    util.the = ($element) => $element[0];

    tippy_default_stub = (element, options) => {
        tippy_target = element;
        tippy_content = options.content;
        assert.equal(options.appendTo(), body_stub);
    };

    const $element = $.create("#folder_filter_widget");
    $element.selector = "#folder_filter_widget";
    $element[0] = {_tippy: {destroy: noop}, id: "folder_filter_widget"};

    folder_dropdown_widget.update_tooltip_for_folder_filter(
        "folder_filter_widget",
        folder_dropdown_widget.FOLDER_FILTERS.ANY_FOLDER_DROPDOWN_OPTION,
    );

    assert.equal(tippy_target.id, "folder_filter_widget");
    assert.equal(tippy_content, "translated: Filter by folder");
});

run_test("update_tooltip_for_folder_filter - Uncategorized", () => {
    initialize_folders();
    let tippy_content;

    util.the = ($element) => $element[0];

    tippy_default_stub = (_element, options) => {
        tippy_content = options.content;
    };

    const $element = $.create("#folder_filter_widget");
    $element.selector = "#folder_filter_widget";
    $element[0] = {_tippy: {destroy: noop}};

    folder_dropdown_widget.update_tooltip_for_folder_filter(
        "folder_filter_widget",
        folder_dropdown_widget.FOLDER_FILTERS.UNCATEGORIZED_DROPDOWN_OPTION,
    );

    assert.equal(tippy_content, "translated: Viewing uncategorized channels");
});

run_test("update_tooltip_for_folder_filter - specific folder", () => {
    const folders = initialize_folders();
    let tippy_content;

    util.the = ($element) => $element[0];

    tippy_default_stub = (_element, options) => {
        tippy_content = options.content;
    };

    const $element = $.create("#folder_filter_widget");
    $element.selector = "#folder_filter_widget";
    $element[0] = {_tippy: {destroy: noop}};

    folder_dropdown_widget.update_tooltip_for_folder_filter(
        "folder_filter_widget",
        folders.frontend_folder.id,
    );

    assert.equal(tippy_content, "translated: Viewing channels in Frontend");
});

run_test("update_tooltip_for_folder_filter - destroy previous tooltip", () => {
    const folders = initialize_folders();
    let destroy_called = false;

    util.the = ($element) => $element[0];

    tippy_default_stub = () => {};

    const $element = $.create("#folder_filter_widget");
    $element.selector = "#folder_filter_widget";
    $element[0] = {
        _tippy: {
            destroy() {
                destroy_called = true;
            },
        },
    };

    folder_dropdown_widget.update_tooltip_for_folder_filter(
        "folder_filter_widget",
        folders.frontend_folder.id,
    );

    assert.ok(destroy_called);
});

run_test("update_tooltip_for_folder_filter - no previous tooltip", () => {
    const folders = initialize_folders();

    util.the = ($element) => $element[0];

    tippy_default_stub = () => {};

    const $element = $.create("#folder_filter_widget");
    $element.selector = "#folder_filter_widget";
    $element[0] = {}; // No _tippy property

    assert.doesNotThrow(() => {
        folder_dropdown_widget.update_tooltip_for_folder_filter(
            "folder_filter_widget",
            folders.frontend_folder.id,
        );
    });
});
