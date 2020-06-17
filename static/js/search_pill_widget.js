exports.initialize = function () {
    if (!page_params.search_pills_enabled) {
        return;
    }
    const container = $('#search_arrows');
    exports.widget = search_pill.create_pills(container);

    exports.widget.createPillonPaste(function () {
        return false;
    });
};

window.search_pill_widget = exports;
