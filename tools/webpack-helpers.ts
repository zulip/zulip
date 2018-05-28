import { basename } from 'path';

/* Return imports-loader format to the config
    For example:
    [
        // Adds 'imports-loader?this=>widndow'
        {path: './foler/my_module.js', args: '?this=>window'},
    ]
*/
interface importLoaderOptions {
   path: string;
   args: string;
}
function getImportLoaders( optionsArr:Array<importLoaderOptions> ) {
    let importsLoaders = [];
    for(var loaderEntry of optionsArr) {
        importsLoaders.push({
            test: require.resolve(loaderEntry.path),
            use: "imports-loader?" + loaderEntry.args
        });
    }
    return importsLoaders;
}
/* Return expose-loader format to the config
    For example
    [
        // Exposes 'my_module' as the name
        {path: './folder/my_module.js'},

        // Exposes 'my_custom_name'
        {path: './folder/my_module.js', name: 'my_custom_name'},

        // Exposes 'name1' and 'name2'
        {path: './folder/my_module.js', name: ['name1', 'name2']}
    ]
*/
interface exportLoaderOptions {
   path: string;
   name?: string | Array<string>;
}
function getExposeLoaders( optionsArr:Array<exportLoaderOptions> ) {
    let exposeLoaders = [];
    for(var loaderEntry of optionsArr) {
        let path = loaderEntry.path;
        let name = "";
        let useArr = [];
        // If no name is provided, infer it
        if(!loaderEntry.name) {
            name = basename(path, '.js');
            useArr.push({loader: 'expose-loader', options: name});
        } else {
            // If name is an array
            if(Array.isArray(loaderEntry.name)) {
                for(var exposeName of loaderEntry.name) {
                    useArr.push({loader: 'expose-loader', options: exposeName})
                }
            // If name is a string
            } else {
                useArr.push({loader: 'expose-loader', options: loaderEntry.name});
            }
        }
        exposeLoaders.push({
            test: require.resolve(path),
            use: useArr
        });
    }
    return exposeLoaders;
}
export {
    getExposeLoaders,
    getImportLoaders
}
