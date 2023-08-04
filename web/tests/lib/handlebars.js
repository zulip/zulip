"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const Handlebars = require("handlebars");
const {version: handlebars_version} = require("handlebars/package");
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

exports.process = (code, filename) => {
    const pc = hb.precompile(code, {preventIndent: true, srcName: filename, strict: true});
    const node = new SourceNode();
    const namespace_path = path.relative(path.dirname(filename), require.resolve("./namespace"));
    node.add([
        'const Handlebars = require("handlebars/runtime");\n',
        "const {template_stub} = require(",
        JSON.stringify("./" + namespace_path),
        ");\n",
        "module.exports = template_stub({filename: ",
        JSON.stringify(filename),
        ", actual_render: Handlebars.template(",
        SourceNode.fromStringWithSourceMap(pc.code, new SourceMapConsumer(pc.map)),
        ")});\n",
    ]);
    const out = node.toStringWithSourceMap();
    return {code: out.code, map: out.map.toString()};
};

const transformer_code = fs.readFileSync(__filename);

exports.getCacheKey = (source_text, source_path, {instrument}) => {
    const relative_path = path.relative(path.dirname(__filename), source_path);
    const data = {transformer_code, handlebars_version, source_text, relative_path, instrument};
    return crypto.createHash("md5").update(JSON.stringify(data)).digest("hex");
};
