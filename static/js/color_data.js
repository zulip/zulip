var color_data = (function () {

var exports = {};

// These colors are used now for streams.
var stream_colors = [
    "#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
    "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
    "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
    "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
    "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
    "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462",
];

// Shuffle our colors on page load to prevent
// bias toward "early" colors.
exports.colors = _.shuffle(stream_colors);

exports.reset = function () {
    exports.unused_colors = exports.colors.slice();
};

exports.reset();

exports.claim_color = function (color) {
    var i = exports.unused_colors.indexOf(color);

    if (i < 0) {
        return;
    }

    exports.unused_colors.splice(i, 1);

    if (exports.unused_colors.length === 0) {
        exports.reset();
    }
};

exports.claim_colors = function (subs) {
    var used_colors = new Dict();

    _.each(subs, function (sub) {
        if (sub.color) {
            used_colors.set(sub.color, true);
        }
    });

    _.each(used_colors.keys(), function (color) {
        exports.claim_color(color);
    });
};

exports.pick_color = function () {
    var color = exports.unused_colors[0];

    exports.claim_color(color);

    return color;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = color_data;
}
window.color_data = color_data;
