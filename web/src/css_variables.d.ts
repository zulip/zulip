/* This is a placeholder typescript declaration file for `css_variables` module.
   We can't convert the `css_variables` module to typescript yet because converting
   it causes Webpack to trigger type checking with the TypeScript compiler, which is very expensive.

   TS-migration of this module was reverted in this PR: https://github.com/zulip/zulip/pull/24985.
*/

declare const css_variables: {
    media_breakpoints: {
        xs_min: string;
        sm_min: string;
        md_min: string;
        mc_min: string;
        lg_min: string;
        xl_min: string;
        ml_min: string;
        mm_min: string;
        ms_min: string;
    };
    media_breakpoints_num: {
        xs: number;
        sm: number;
        md: number;
        mc: number;
        lg: number;
        xl: number;
        ml: number;
        mm: number;
        ms: number;
    };
};

export = css_variables;
