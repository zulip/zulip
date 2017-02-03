import converter

def test():
    for cmd, expected_response in sample_conversation():
        message = {'content': cmd, 'subject': 'foo',
                   'display_recipient': 'bar'}

        class ClientDummy(object):
            def __init__(self):
                self.output = ''

            def send_message(self, params):
                self.output = params['content']
        handler = converter.ConverterHandler()
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
        ('@convert 2 m cm', '2.0 m = 200.0 cm\n'),
        ('@converter 2 m cm', ''),
        ('@convert 12 celsius fahrenheit',
         '12.0 celsius = 53.600054 fahrenheit\n'),
        ('@convert 0.002 kilometer millimile',
         '0.002 kilometer = 1.2427424 millimile\n'),
        ('@convert 3 megabyte kilobit',
         '3.0 megabyte = 24576.0 kilobit\n'),
        (('foo @convert 120.5 g lb bar baz.\n'
          'baz bar bar @convert 22 k c lorem ipsum dolor'),
         ('1. conversion: 120.5 g = 0.26565703 lb\n'
          '2. conversion: 22.0 k = -251.15 c\n')),
        ('@convert foo bar',
         ('Too few arguments given. Enter `@convert help` '
          'for help on using the converter.\n')),
    ]

if __name__ == '__main__':
    test()
