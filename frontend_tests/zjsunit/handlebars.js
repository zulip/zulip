const fs = require("fs");
const path = require("path");

const templates_path = path.resolve(__dirname, "../../static/templates");
let render;

module.exports.make_handlebars = () => {
    // Create a new Handlebars instance.
    const Handlebars = require("handlebars/dist/cjs/handlebars.js");
    const hb = Handlebars.create();

    const compiled = new Map();

    render = (filename, ...args) => {
        if (!compiled.has(filename)) {
            compiled.set(filename, hb.compile(fs.readFileSync(filename, "utf-8")));
        }
        return compiled.get(filename)(...args);
    };

    return hb;
};

module.exports.stub_templates = stub => {
    set_global("Handlebars", module.exports.make_handlebars());
    zrequire("templates");
    render = (filename, ...args) => {
        const name = path.relative(templates_path, filename).slice(0, -".hbs".length);
        return stub(name, ...args);
    };
};

require.extensions[".hbs"] = (module, filename) => {
    module.exports = (...args) => render(filename, ...args);
};
