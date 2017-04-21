 ____________________________________________________________________
|                                                                    |
|    _____ _                                       ____        _      |
|   / ____(_)                                     |  _ \      | |     |
|  | |  __ ___   _____  __ ___      ____ _ _   _  | |_) | ___ | |_    |
|  | | |_ | \ \ / / _ \/ _` \ \ /\ / / _` | | | | |  _ < / _ \| __|   |
|  | |__| | |\ V /  __/ (_| |\ V  V / (_| | |_| | | |_) | (_) | |_    |
|   \_____|_| \_/ \___|\__,_| \_/\_/ \__,_|\__, | |____/ \___/ \__|   |
|                                           __/ |                     |
|                                          |___/                      |
|_____________________________________________________________________|
|                                                                     |
|Zulip Giveaway Bot - Created By Daniel O'Brien                       |
|_____________________________________________________________________|
|Overview:                                                            |
|                                                                     |
|This bot facilitates the creation of 'Giveaways' within Zuilip. Once |
|a giveaway has been initiated, it will automatically count down for  |
|a set period of time and once that time has passed it will randomly  |
|choose a winner out of the people whom entered the giveaway in that  |
|time period                                                          |
|_____________________________________________________________________|
|Syntax:                                                              |
|                                                                     |
|@giveaway init|enter|exit|cancel [giveaway_name] [giveaway_time]     |
|_____________________________________________________________________|
|Commands:                                                            |
|                                                                     |
|    - init: Initialise a giveaway, [giveaway_name] and               |
|      [giveaway_time] must also be supplied.                         |
|                                                                     |
|    - enter: Enter a giveaway, requires for there to already be an   |
|      active giveaway to work.                                       |
|                                                                     |
|    - exit: Exit a giveaway, requires for there to be an active      |
|      giveaway in which the user is already partaking.               |
|                                                                     |
|    - cancel: Cancel a giveaway, requires for there already to be    |
|      an active giveaway. Can only be executed by the creator of     |
|      the giveaway.                                                  |
|_____________________________________________________________________|
| giveaway_name: The name of the giveaway the user wishes to create.  |
| Must be 1 word/several words separated with dashes or underscores.  |
|_____________________________________________________________________|
| giveaway_time: The time, in minutes, the user wishes the giveaway to|
| go on for. Maximum of 100 mins to prevent a stack overflow.         |
|_____________________________________________________________________|
|                           |Example Usage|                           |
|___________________________|_____________|___________________________|
|              COMMAND             |           EXPLANATION            |
|__________________________________|__________________________________|
|                                  | This command will create a       |
|     @giveaway init Foobar 10     | giveaway called "Foobar" which   |
|                                  | will last for 10 minutes.        |
|__________________________________|__________________________________|
|                                  | This command will enter the user |
|                                  | whom executed this command in    |
|          @giveaway enter         | whatever giveaway is currently   |
|                                  | running.                         |
|__________________________________|__________________________________|
|                                  | Opposite of @giveaway enter (see |
|          @giveaway exit          | above).                          |
|__________________________________|__________________________________|
|                                  | This command will cancel any     |
|                                  | giveaway that is currently       |
|         @giveaway cancel         | running. Can only be executed by |
|                                  | the person whom created the      |
|                                  | giveaway in the first place.     |
|__________________________________|__________________________________|


