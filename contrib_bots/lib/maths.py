# See readme.md for instructions on running this code.
import operator

class MathsHandler(object):
    '''
    This plugin allows you to complete maths equations 
    quickly when in the middle of a chat. It looks for 
    @maths and @math.

    This bot sends the maths solutions to the
    stream from which they are sent. More operations can 
    easily be added by creating a function for each operation.
    
    An example use case of the bot is '@maths 4 * 12'
    This will return (To the current stream):
    
    '''

    def usage(self):
        return '''
            This plugin will allow users to complete maths
            calculations. Users should preface
            messages with "@maths or @math".

            Make sure to use this in the stream in which you want the answer.
            If you want to keep it private, send a private message to the
            bot.
            
            This bot currently contains only:
            Addition : +
            Multiplication : *
            Subtraction: -
            Division: /
            '''

    def triage_message(self, message):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']
        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups!
        if message['display_recipient'] == 'followup':
            return False
        is_follow_up = (original_content.startswith('@maths') or
                        original_content.startswith('@math'))

        return is_follow_up
        
    def is_number(self,x): #Checks whether a string is a number or not (used for confirming user input)
        try:
            float(x)
            return True
        except ValueError:
            return False
    
    def do_maths(self,maths_nums,maths_ops):

        maths_nums = list(maths_nums)
        maths_ops = list(maths_ops)
        operator_order = ('*/','+-')  #order of operations goes from left to right. Operators at the same level have the same 'importance'
        #If adding operators, remember to add them here ^^^^ as well
        #Assign operators to the operator functions 
        op_dict = {'*':operator.mul, '/':operator.div, '+':operator.add, '-':operator.sub} # You can add your own operators here
        Value = None
        for x in operator_order:                   #Loop over levels of 'importance'
            while any(o in maths_ops for o in x):        #Operator with this importance exists
                idx,oo = next((i,o) for i,o in enumerate(maths_ops) if o in x) #Next operator with this precedence         
                maths_ops.pop(idx)                        #remove this operator from the operator list
                values = map(float,maths_nums[idx:idx+2]) #here I just assume float for everything
                value = op_dict[oo](*values)
                maths_nums[idx:idx+2] = [value]           #clear out those indices

        return maths_nums[0]
        
    def parse_expression(self, message_content):
    #Determines the operation which is being used and parses the expression
        
        calc = message_content.replace('@maths','')
        maths_exp = calc.replace('@math','') #Used for Bot response later
        calc = ''.join(maths_exp.split())
        operators = set('+-*/') #If adding operators, remember to add them here as well
        ops = []    #Operators in string 
        nums = []   #Non-operators
        buffer = [] #Buffer
        error = False #Math Error Boolean
        prevval = None #Var containing the previous value (Operator or Number)
        negnum = False #Var for creating negative numbers
        charnum = 0 #Number of char in calculation
        for i in calc:  #Look at each character
            charnum += 1
            if negnum == True:
                i = "-"+i
                negnum = False
            if (i in operators) and (prevval is not None) and (prevval != "op") and charnum != len(calc):  #Check for valid operators
                nums.append(''.join(buffer))
                buffer = []
                ops.append(i)
                prevval = "op"
            elif i == "-" and charnum != len(calc):
                negnum = True
                prevval = "op"
            elif self.is_number(i):
            #Stuff that isn't operators.These characters go to the buffer.
                buffer.append(i)
                prevval = "num"
            else:
                print "There is an Error"
                error = True
        nums.append(''.join(buffer))
            
        return nums, ops, error, maths_exp
        

        
    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']
        original_subject = message['subject']
        sender_name = message['sender_full_name']
        maths_vals = self.parse_expression(original_content) #Gets the results of the parsing including the numbers used, operations used, error status and original expression
        original_expression = maths_vals[3] #Used in bot response
        if maths_vals[2] == False:
            answer = self.do_maths(maths_vals[0],maths_vals[1])
            new_content = "@**"+sender_name+"** Mathsbot:"+original_expression+" = "+str(answer) #Answer message
        else:
            new_content = "@**"+sender_name+"** Mathsbot: There is an error with"+original_expression+". You may have used an unknown/incorrect operator or left out a number/operator :slightly_frowning_face:" #Error Message
        
        
        if message['type'] == 'private': #Code for a Private Message to the bot

            client.send_message(dict(
                type='private',
                to=original_sender,
                content=new_content,
            ))
        else: #Code for a Stream Message to the bot
            
            client.send_message(dict(
                type='stream',
                subject=original_subject,
                to=message['display_recipient'],
                content=new_content,
            ))
            
            

handler_class = MathsHandler
