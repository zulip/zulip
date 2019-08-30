module.exports = ({ file, options }) => ({
    parser: file.extname === ".scss" ? "postcss-scss" : false,
    plugins: {
        // Warning: despite appearances, order is significant
        "postcss-nested": {},
        "postcss-extend-rule": {},
        "postcss-simple-vars": {},
        "postcss-calc": {},
        autoprefixer: {},
        cssnano: options.env === "production" ? {} : false,
    },
});
