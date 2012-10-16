import logging

logger = logging.getLogger('humbug.requests')

class LogRequests(object):
    def process_response(self, request, response):

        # The reverse proxy might have sent us the real external IP
        remote_ip = request.META.get('HTTP_X_REAL_IP')
        if remote_ip is None:
            remote_ip = request.META['REMOTE_ADDR']

        logger.info('%-15s %-7s %3d %s'
            % (remote_ip, request.method, response.status_code, request.get_full_path()))
        return response
