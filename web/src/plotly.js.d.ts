// An internal type extracted from @types/plotly.js
// pie and bar are both trace modules from the traces subdirectory
type TraceModule = {
    [key: string]: unknown;
    moduleType: "trace";
    name: string;
    categories: string[];
    meta: Record<string, unknown>;
};

declare module "plotly.js/lib/pie" {
    const PlotlyPie: TraceModule;
    export = PlotlyPie;
}

declare module "plotly.js/lib/bar" {
    const PlotlyBar: TraceModule;
    export = PlotlyBar;
}
