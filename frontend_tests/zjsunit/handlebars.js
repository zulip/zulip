const fs = require("fs");
const path = require("path");

const templates_path = path.resolve(__dirname, "../../static/templates");
let render;

exports.make_handlebars = () => {
    // Create a new Handlebars instance.
    const Handlebars = require("handlebars/dist/cjs/handlebars.js");
    const hb = Handlebars.create();

    const compiled = new Set();
    const compileFile = filename => {
        const name = "$" + path.relative(templates_path, filename);
        if (!compiled.has(name)) {
            compiled.add(name);
            hb.registerPartial(
                name,
                hb.compile(fs.readFileSync(filename, "utf-8"), { preventIndent: true, zjsFilename: filename })
            );
        }
        return name;
    };

    class ZJavaScriptCompiler extends hb.JavaScriptCompiler {
        nameLookup(parent, name, type) {
            // Auto-register partials with relative paths, like handlebars-loader.
            if (type === "partial" && name !== "@partial-block") {
                name = compileFile(path.resolve(path.dirname(this.options.zjsFilename), name + ".hbs"));
            }
            return super.nameLookup(parent, name, type);
        }
    }

    ZJavaScriptCompiler.prototype.compiler = ZJavaScriptCompiler;
    hb.JavaScriptCompiler = ZJavaScriptCompiler;

    render = (filename, ...args) => hb.partials[compileFile(filename)](...args);

    return hb;
};

exports.stub_templates = stub => {
    render = (filename, ...args) => {
        const name = path.relative(templates_path, filename).slice(0, -".hbs".length);
        return stub(name, ...args);
    };
};

require.extensions[".hbs"] = (module, filename) => {
    module.exports = (...args) => render(filename, ...args);
};
