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

module.exports = ({ file }) => {
    let opts = {
        parser: file.extname === ".scss" ? "postcss-scss" : false,
        plugins: {
            // Warning: despite appearances, order is significant
            "postcss-nested": {},
            "postcss-extend-rule": {},
            "postcss-simple-vars": {},
            "postcss-calc": {},
            "postcss-wrap": false, // Maybe add the plugin at this position
            autoprefixer: {},
        },
    };
    opts = maybe_handle_flatpickr(file, opts);
    return opts;
};
