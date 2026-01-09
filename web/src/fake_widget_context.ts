import type { Message } from "./message_store";

export class ZulipWidgetContext {

    constructor(message: Message) {
       
    }

    is_container_hidden(): boolean {
        return false;
    }

    is_my_poll(): boolean {
        return true
    }

    owner_user_id(): number {
        return 1
    }
    current_user_id():number{
        return 1;
    }
    get_full_name_list(user_ids:number[]):string{
        return user_ids.map((id)=>`user${id}`).join(', ')
    }
}
