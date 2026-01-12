class FakePeople{
    is_my_user_id(id:number):boolean{
        return true;
    }
    my_current_user_id():number{
        return 1
    }
    get_full_names_for_poll_option(user_ids:number[]){
        const names = []
        for(let id of user_ids){
            if(id===1){
                names.push("apoorva")
            }
        }
        return names.join(", ")
    }
}

const people =  new FakePeople()
export default people