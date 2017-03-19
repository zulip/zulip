/*

This module has shims to help us break circular dependencies.
We eventually want to to move the actual implementations into
new modules.  When we do this, you may need to fix node tests
that still refer to the old name.
*/

var narrow_state = {}; // global, should be made into module
narrow_state.set_compose_defaults = narrow.set_compose_defaults;

var compose_actions = {};
compose_actions.start = compose.start;
compose_actions.cancel = compose.cancel;

var compose_state = {};
compose_state.has_message_content = compose.has_message_content;
compose_state.recipient = compose.recipient;
compose_state.composing = compose.composing;

var ui_report = {};
ui_report.success = ui.report_success;
ui_report.error = ui.report_error;
ui_report.message= ui.report_message;
