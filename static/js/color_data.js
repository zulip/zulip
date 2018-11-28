var color_data = (function () {

var exports = {};

// Auto-assigned colors should be from the default palette so it's easy to undo
// changes, so if that palette changes, change these colors.
var stream_assignment_colors = [
    "#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
    "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
    "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
    "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
    "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
    "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462",
];

exports.pick_color = function (used_colors) {
    var colors = _.shuffle(stream_assignment_colors);
    var used_color_hash = {};

    _.each(used_colors, function (color) {
        used_color_hash[color] = true;
    });

    var color = _.find(colors, function (color) {
        return !_.has(used_color_hash, color);
    });

    if (color) {
        return color;
    }

    // All available colors were used.
    return colors[0];
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = color_data;
}
window.color_data = color_data;
