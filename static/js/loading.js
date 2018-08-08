var loading = (function () {

var exports = {};

exports.make_indicator = function (outer_container, opts) {
    opts = opts || {};
    var container = outer_container;

    // TODO: We set white-space to 'nowrap' because under some
    // unknown circumstances (it happens on Keegan's laptop) the text
    // width calculation, above, returns a result that's a few pixels
    // too small.  The container's div will be slightly too small,
    // but that's probably OK for our purposes.
    outer_container.css({display: 'block',
                         'white-space': 'nowrap'});

    container.empty();

    if (opts.abs_positioned !== undefined && opts.abs_positioned) {
        // Create some additional containers to facilitate absolutely
        // positioned spinners.
        var container_id = container.attr('id');
        var inner_container = $('<div id="' + container_id + '_box_container"></div>');
        container.append(inner_container);
        container = inner_container;
        inner_container = $('<div id="' + container_id + '_box"></div>');
        container.append(inner_container);
        container = inner_container;
    }

    var spinner_elem = $('<div class="loading_indicator_spinner"></div>');
    spinner_elem.html(templates.render("loader", { container_id: outer_container.attr("id") }));
    container.append(spinner_elem);
    var text_width = 0;

    if (opts.text !== undefined && opts.text !== '') {
        var text_elem = $('<span class="loading_indicator_text"></span>');
        text_elem.text(opts.text);
        container.append(text_elem);
        // See note, below
        if (!(opts.abs_positioned !== undefined && opts.abs_positioned)) {
            text_width = 20 + text_elem.width();
        }
    }

    // These width calculations are tied to the spinner width and
    // margins defined via CSS
    container.css({width: 38 + text_width,
                   height: 0});

    outer_container.data("destroying", false);
};

exports.destroy_indicator = function (container) {
    if (container.data("destroying")) {
        return;
    }
    container.data("destroying", true);

    var spinner = container.data("spinner_obj");
    if (spinner !== undefined) {
        spinner.stop();
    }
    container.removeData("spinner_obj");
    container.empty();
    container.css({width: 0, height: 0, display: 'none'});
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = loading;
}
window.loading = loading;
