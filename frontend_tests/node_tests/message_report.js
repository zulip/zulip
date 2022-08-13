"use strict";

const {strict: assert} = require("assert");

const {register_report_message_click_handlers} = require("../../static/js/popovers");
const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const channel = mock_esm("../../static/js/channel");
const message_lists = mock_esm("../../static/js/message_lists");
const message_report = zrequire("../../static/js/message_report");
const message_viewport = mock_esm("../../static/js/message_viewport");
let modal_open = false;
const overlays = mock_esm("../../static/js/overlays", {
    close_overlay: () => {},
    close_active: () => {},
    open_overlay: () => {},
    is_modal_open: () => modal_open,
    open_modal: () => {
        modal_open = true;
        return true;
    },
    close_modal: () => {
        modal_open = false;
        return true;
    },
});
const rows = mock_esm("../../static/js/rows");

let payload_post;
let dialog_html;

let cnt = 0;
function mock_dialog_template(mock_template, mymsg) {
    mock_template("dialog_widget.hbs", true, (data, html) => {
        cnt += 1;
        assert.equal(data.heading_text, "translated HTML: Alert");
        assert.match(html, new RegExp(mymsg));
        const $dialog = $.create("dialog" + cnt.toString());
        const $submit_button = $.create("submit_button" + cnt.toString());
        $dialog.set_find_results(".dialog_submit_button", $submit_button);
        const $send_email_checkbox = $.create("send_email_checkbox" + cnt.toString());
        $dialog.set_find_results(".send_email", $send_email_checkbox);
        const $email_field = $.create("email_field" + cnt.toString());
        $dialog.set_find_results(".email_field", $email_field);
        dialog_html = html;
        return $dialog;
    });
}

const $row = $.create("row");
const $target = $.create("target");
const $report_message = $.create("report_message");
const $nonbut = $.create("nonbut");
const $cancelbut = $.create("cancelbut");
const $submitbut = $.create("submitbut");
const message = {id: 111, raw_content: "origmsg"};

let post_action = "success";

function clear(override) {
    $.clear_all_elements();
    $nonbut.off("click");
    $cancelbut.off("click");
    $submitbut.off("click");
    payload_post = undefined;
    post_action = "success";

    override(channel, "post", (arg) => {
        payload_post = arg;
        // console.log('post:');console.log(payload_post);
        if (payload_post.success !== undefined) {
            if (post_action === "success") {
                payload_post.success();
            } else {
                payload_post.error({responseJSON: {msg: "my_errmsg"}});
            }
        }
    });
}

function assert_post_not_called() {
    assert.equal(payload_post, undefined);
    channel.post("");
}

function setup(mock_template, reason, explanation) {
    message_lists.current = {};
    message_lists.current.get = (message_id) => message;
    rows.id = ($row) => 111;
    message_lists.current.get_row = (message_id) => {
        assert.equal(message_id, 111);
        $target.safeOuterHeight = () => 123;
        $row.set_find_results(".messagebox-content", $target);
        $row.safeOuterWidth = () => 345;
        $target.set_find_results(".report_message-box", {
            remove: () => {},
            css: (string, val) => {
                assert.equal(string, "width");
                assert.equal(val, "291px");
            },
        });
        $report_message.slideDown = (easing, func) => {
            assert.equal(easing, 600);
            assert.equal(typeof func, "function");
            message_viewport.$message_pane = {
                animate: (opts, easing2) => {
                    assert.deepEqual(opts, {scrollTop: 125});
                    assert.equal(easing2, 600);
                },
            };
            func();
        };
        $report_message.slideUp = (easing, func) => {
            assert.equal(easing, 400);
            assert.equal(func, undefined);
        };
        $report_message.set_find_results("div,label,input[type=radio]", $nonbut);
        $report_message.set_find_results("button.report_message_cancel", $cancelbut);
        $report_message.set_find_results("button.report_message_submit", $submitbut);
        $row.set_find_results(".report_message-box", $report_message);
        return $row;
    };
    message_lists.current.select_id = (message_id, opts) => {
        assert.equal(message_id, 111);
        assert.deepEqual(opts, {then_scroll: true});
    };
    message_lists.current.view = {};
    message_viewport.$message_pane = {
        scrollTop: () => 42,
    };
    $report_message.set_find_results("input[type=radio][name=report_message-reason]:checked", {
        val: () => reason,
    });
    $report_message.set_find_results("textarea[name=report_message-explain]", {
        val: () => explanation,
    });
    mock_template(
        "report_message.hbs",
        true,
        (data, html) =>
            // assert more specific things about the data ?
            html,
    );
}

run_test("error_dialog", ({mock_template}) => {
    const mymsg = "my_error_dialog";
    mock_dialog_template(mock_template, mymsg);
    message_report.msgreport_alert(mymsg);
    overlays.close_modal();
    assert.ok(!overlays.is_modal_open());
    assert.ok(dialog_html.includes(mymsg));
});

run_test("clicking", ({override, mock_template}) => {
    clear(override);
    setup(mock_template, "reason", "explanation");
    mock_dialog_template(mock_template, "");
    message_report.show_report_dialog(
        {id: 111, raw_content: "myrawcontent"},
        register_report_message_click_handlers,
    );
    let calls = 0;
    $nonbut.get_on_handler("click")({
        stopPropagation: () => {
            calls += 1;
        },
    });
    $cancelbut.get_on_handler("click")({
        stopPropagation: () => {
            calls += 1;
        },
        preventDefault: () => {
            calls += 1;
        },
    });
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {
            calls += 1;
        },
        preventDefault: () => {
            calls += 1;
        },
    });
    assert.equal(calls, 5);
    assert_post_not_called();
});

run_test("click_submit_spam_foo", ({override, mock_template}) => {
    clear(override);
    setup(mock_template, "spam", "\n \nmy explanation\n \n ");
    message_report.show_report_dialog(
        {id: 111, raw_content: false},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.equal(payload_post.data.explanation, "\n \nmy explanation\n \n ");
});

run_test("click_submit_spam_empty", ({override, mock_template}) => {
    clear(override);
    setup(mock_template, "spam", "");
    message_report.show_report_dialog(
        {id: 111, raw_content: false},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.equal(payload_post.data.explanation, "");
});

run_test("click_submit_badreason_dne", ({override, mock_template}) => {
    clear(override);
    const mymsg = "Please select a reason";
    setup(mock_template, "doesntexist", "");
    mock_dialog_template(mock_template, mymsg);
    message_report.show_report_dialog(
        {id: 111, raw_content: false},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.ok(dialog_html.includes(mymsg));
    assert_post_not_called();
});

run_test("click_submit_badreason_undefined", ({override, mock_template}) => {
    clear(override);
    const mymsg = "Please select a reason";
    setup(mock_template, undefined, "");
    mock_dialog_template(mock_template, mymsg);
    message_report.show_report_dialog(
        {id: 111, raw_content: false},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.ok(dialog_html.includes(mymsg));
    assert_post_not_called();
});

run_test("click_submit_badreason_empty", ({override, mock_template}) => {
    clear(override);
    const mymsg = "Please select a reason";
    setup(mock_template, "", "");
    mock_dialog_template(mock_template, mymsg);
    message_report.show_report_dialog(
        {id: 111, raw_content: false},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.ok(dialog_html.includes(mymsg));
    assert_post_not_called();
});
run_test("click_submit_other_empty", ({override, mock_template}) => {
    clear(override);
    const mymsg = "requires an explanation";
    setup(mock_template, "other", "");
    mock_dialog_template(mock_template, mymsg);
    message_report.show_report_dialog(
        {id: 111, raw_content: false},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.ok(dialog_html.includes(mymsg));
    assert_post_not_called();
});
run_test("click_submit_other_undefined", ({override, mock_template}) => {
    clear(override);
    const mymsg = "requires an explanation";
    setup(mock_template, "other", undefined);
    mock_dialog_template(mock_template, mymsg);
    message_report.show_report_dialog(
        {id: 111, raw_content: false},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.ok(dialog_html.includes(mymsg));
    assert_post_not_called();
});
run_test("click_submit_norms_msgrawcontent", ({override, mock_template}) => {
    clear(override);
    const mymsg = "requires an explanation";
    setup(mock_template, "norms", "myexplanation");
    message_report.show_report_dialog(
        {id: 111, raw_content: "myrawcontent"},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.ok(dialog_html.includes(mymsg));
});
run_test("click_submit_server_error", ({override, mock_template}) => {
    clear(override);
    post_action = "error";
    const mymsg = "Failure reporting message";
    setup(mock_template, "norms", "myexplanation");
    mock_dialog_template(mock_template, mymsg);
    message_report.show_report_dialog(
        {id: 111, raw_content: "myrawcontent"},
        register_report_message_click_handlers,
    );
    $submitbut.get_on_handler("click")({
        stopPropagation: () => {},
        preventDefault: () => {},
    });
    assert.ok(dialog_html.includes(mymsg));
});

run_test("random_coverage", ({override, mock_template}) => {
    clear(override);
    /* eslint no-unused-vars: ["error", { "args": "none" }]*/
    message_lists.current.get_row = (ignored_inputs) => undefined;
    message_report.show_report_dialog({id: 42});
    assert_post_not_called();
});
