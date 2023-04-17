type Hook = () => void;
type Hook_ = (param: any) => void;

let notification_hook : Hook[] = []                 //1
let hashchange_activate_hook : Hook_[] = []          //2
let hashchange_deactivate_hook : Hook[] = []        //3
let stream_list_activate_hook : Hook_[] = []          //4
let stream_list_deactivate_hook : Hook[] = []        //5


//1 notification - redraw_title
export function register_notification_hook(func: Hook) :void {
    notification_hook.push(func);
}

export function call_notification_hook() : void {
    for (let func of notification_hook) {
        func();
    }
}


//2 hashchange - save_narrow
export function register_hashchange_activate_hook(func: Hook) :void {
    hashchange_activate_hook.push(func);
}

export function call_hashchange_activate_hook(param: any) : void {
    for (let func of hashchange_activate_hook) {
        func(param);
    }
}


//3 hashchange - save_narrow
export function register_hashchange_deactivate_hook(func: Hook) :void {
    hashchange_deactivate_hook.push(func);
}

export function call_hashchange_deactivate_hook() : void {
    for (let func of hashchange_deactivate_hook) {
        func();
    }
}


//4 stream_list - handle_narrow_activated
export function register_stream_list_activate_hook(func: Hook) :void {
    stream_list_activate_hook.push(func);
}

export function call_stream_list_activate_hook(param: any) : void {
    for (let func of stream_list_activate_hook) {
        func(param);
    }
}


//5 stream_list - handle_narrow_deactivated
export function register_stream_list_deactivate_hook(func: Hook) :void {
    stream_list_deactivate_hook.push(func);
}

export function call_stream_list_deactivate_hook() : void {
    for (let func of stream_list_deactivate_hook) {
        func();
    }
}
