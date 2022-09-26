declare module "*.hbs" {
    const render: (context: unknown) => string;
    export = render;
}
