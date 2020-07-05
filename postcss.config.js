const maybe_handle_flatpickr = (file, opts) => {
    // We want to wrap flatpickr's dark theme in our night-mode class
    // so we can switch themes easily.
    if (file.basename === 'dark.css' && file.dirname.includes('flatpickr/dist/themes')) {
        opts.plugins['postcss-wrap'] = {
            selector: "body.night-mode",
        };
    }
    return opts;
};

const maybe_append_prefered_color_scheme = (file, opts) => {
    // If a file contains night-mode specific CSS, add it here:
    const night_mode_files = [
        'night_mode.scss',
    ];

    const data = `
@media (prefers-color-scheme: dark) {
    body.color-scheme-automatic {
        @extend body.night-mode;
    }
}`;
    const flatpickr = file.basename === 'dark.css' && file.dirname.includes('flatpickr/dist/themes');
    if (night_mode_files.includes(file.basename) || flatpickr) {
        opts.plugins['postcss-raw-append'] = { data };
    }
    return opts;
};

module.exports = ({ file }) => {
    let opts = {
        parser: file.extname === ".scss" ? "postcss-scss" : false,
        plugins: {
            // Warning: despite appearances, order is significant
            "postcss-wrap": false, // Maybe add the plugin at this position
            "postcss-raw-append": false,
            "postcss-nested": {},
            "postcss-extend-rule": {},
            "postcss-simple-vars": {},
            "postcss-calc": {},
            autoprefixer: {},
        },
    };
    opts = maybe_handle_flatpickr(file, opts);
    opts = maybe_append_prefered_color_scheme(file, opts);
    return opts;
};
