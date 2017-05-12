import encrypt_bot

def test():
    for cmd, expected_response in sample_conversation():
        message = {'content': cmd, 'subject': 'foo',
                   'display_recipient': 'bar'}

        class ClientDummy(object):
            def __init__(self):
                self.output = ''

            def send_message(self, params):
                self.output = params['content']
        handler = encrypt_bot.EncryptHandler()
        client_dummy = ClientDummy()
        handler.handle_message(message, client_dummy, '')
        if client_dummy.output != expected_response:
            raise AssertionError('''
                cmd: %s
                expected: %s
                but got : %s
                ''' % (cmd, expected_response, client_dummy.output))

def sample_conversation():
    return [
        ('@encrypt Please encrypt this', 'Encrypted/Decrypted text:  Cyrnfr rapelcg guvf'),
        ('@encrypt Let\'s Do It', 'Encrypted/Decrypted text:  Yrg\'f Qb Vg'),
        ('@encrypt ', 'Encrypted/Decrypted text:  '),
        ('@encrypt me&mom together..!!', 'Encrypted/Decrypted text:  zr&zbz gbtrgure..!!'),
    ]

if __name__ == '__main__':
    test()
