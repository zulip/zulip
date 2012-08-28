import type {Linter, Rule} from "eslint";

declare const pluginPromise: {
    rules: Record<string, Rule.RuleModule>;
    configs: {
        recommended: Linter.LegacyConfig;
        "flat/recommended": Linter.Config;
    };
};
export = pluginPromise;
