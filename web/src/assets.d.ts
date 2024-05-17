declare module "*.svg" {
    const url: string;
    export default url;
}

declare module "*.ttf" {
    const url: string;
    export default url;
}

declare module "*.png" {
    const url: string;
    export default url;
}

// Declare the style loader for CSS files.  This is used in the
// `import` statements in the `emojisets.ts` file.
declare module "!style-loader?*" {
    const css: {use: () => void; unuse: () => void};
    export default css;
}
