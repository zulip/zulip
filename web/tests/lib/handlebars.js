"use strict";

const fs = require("fs");
const path = require("path");

const Handlebars = require("handlebars");
const {SourceMapConsumer, SourceNode} = require("source-map");

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

function compile_hbs(module, filename) {
    const code = fs.readFileSync(filename, "utf8");
    const pc = hb.precompile(code, {preventIndent: true, srcName: filename, strict: true});
    const node = new SourceNode();
    node.add([
        'const Handlebars = require("handlebars/runtime");\n',
        "module.exports = Handlebars.template(",
        SourceNode.fromStringWithSourceMap(pc.code, new SourceMapConsumer(pc.map)),
        ");\n",
    ]);
    const out = node.toStringWithSourceMap();
    module._compile(
        out.code +
            "\n//# sourceMappingURL=data:application/json;charset=utf-8;base64," +
            Buffer.from(out.map.toString()).toString("base64"),
        filename,
    );
}

exports.hook_require = () => {
    require.extensions[".hbs"] = compile_hbs;
};
