"use strict";

const fs = require("fs");
const path = require("path");

const Handlebars = require("handlebars");
const {SourceMapConsumer, SourceNode} = require("source-map");

const templates_path = path.resolve(__dirname, "../../static/templates");

exports.stub_templates = (stub) => {
    window.template_stub = stub;
};

const hb = Handlebars.create();

class ZJavaScriptCompiler extends hb.JavaScriptCompiler {
    nameLookup(parent, name, type) {
        // Auto-register partials with relative paths, like handlebars-loader.
        if (type === "partial" && name !== "@partial-block") {
            const filename = path.resolve(path.dirname(this.options.srcName), name + ".hbs");
            return ["require(", JSON.stringify(filename), ")"];
        }
        return super.nameLookup(parent, name, type);
    }
}

ZJavaScriptCompiler.prototype.compiler = ZJavaScriptCompiler;
hb.JavaScriptCompiler = ZJavaScriptCompiler;

require.extensions[".hbs"] = (module, filename) => {
    const code = fs.readFileSync(filename, "utf-8");
    const name = path.relative(templates_path, filename).slice(0, -".hbs".length);
    const pc = hb.precompile(code, {preventIndent: true, srcName: filename});
    const node = new SourceNode();
    node.add([
        'const Handlebars = require("handlebars/runtime");\n',
        "const template = Handlebars.template(",
        SourceNode.fromStringWithSourceMap(pc.code, new SourceMapConsumer(pc.map)),
        ");\n",
        "module.exports = (...args) => {\n",
        "    if (window.template_stub !== undefined) {\n",
        "        return window.template_stub(",
        JSON.stringify(name),
        ", ...args);\n",
        "    }\n",
        "    return template(...args);\n",
        "};\n",
    ]);
    const out = node.toStringWithSourceMap();
    module._compile(
        out.code +
            "\n//# sourceMappingURL=data:application/json;charset=utf-8;base64," +
            Buffer.from(out.map.toString()).toString("base64"),
        filename,
    );
};
