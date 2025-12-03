import type {PluginCreator} from "postcss";

export type PostCSSExtendRuleOptions = {
    onFunctionalSelector?: "remove" | "ignore" | "warn" | "throw";
    onRecursiveExtend?: "remove" | "ignore" | "warn" | "throw";
    onUnusedExtend?: "remove" | "ignore" | "warn" | "throw";
};

declare const postcssExtendRule: PluginCreator<PostCSSExtendRuleOptions>;
export default postcssExtendRule;
