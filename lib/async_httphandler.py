#!/usr/bin/env python

# This http server module use socket_engine.py as backend.
# I've borrow some code from BaseHTTPServer.py, 
# since a async server is different from synchronized one,
# the underlayer have to be rewriten.
#
#
# plan <frostyplanet@gmail.com>
# 2011-08-03

from lib.socket_engine import TCPSocketEngine
import time
import sys


__version__ = "0.1"

DEFAULT_ERROR_MESSAGE = """\
<head>
<title>Error response</title>
</head>
<body>
<h1>Error response</h1>
<p>Error code %(code)d.
<p>Message: %(message)s.
<p>Error code explanation: %(code)s = %(explain)s.
</body>
"""

DEFAULT_ERROR_CONTENT_TYPE = "text/html"

def _quote_html(html):
    return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class InvalidHeader(Exception):
    pass

class Rfc822Headers(object):

    headers = None

    def __init__(self):
        self.headers = dict()
    
    def add_header(self, name, val):
        self.headers[name] = val

    def get(self, name, default=None):
        return self.headers.get(name, default)

    def pack(self):
        lines = map(lambda x: "%s: %s" % (x[0], x[1]), self.headers.items())
        buf = "\r\n".join(lines)
        if lines:
            buf += "\r\n"
        return buf

    def unpack(self, lines):
        for line in lines:
            arr = line.split(":")
            if len(arr) < 2:
                raise InvalidHeader()
            name = arr[0]
            val = "".join(arr[1:])
            self.add_header(name, self.unpack_field_value(val))
 
    def unpack_field_value(s):
        s = s.strip()
        #TODO
        #p = s.index("(")
        return s
    unpack_field_value = staticmethod(unpack_field_value)

    def __str__(self):
        lines = map(lambda x: x[0] + ":" + x[1] , self.headers.items())
        return "\n".join(lines)


class ClientInfo(object):
    __slots__ = 'conn', 'command', 'path', 'request_version', \
            'close_connection', 'headers', 'temp', \
            'response_code', 'content_length'


class baseHTTPHandler(object):

    LINE_MAX_LENGTH = 10240
    error_message_format = DEFAULT_ERROR_MESSAGE
    error_content_type = DEFAULT_ERROR_CONTENT_TYPE

    server_version = "BaseHTTP/" + __version__
    # The default request version.  This only affects responses up until
    # the point where the request line is parsed, so it mainly decides what
    # the client gets back when sending a malformed request line.
    # Most web servers default to HTTP 0.9, i.e. don't send a status line.
    default_request_version = "HTTP/0.9"

    protocol_version = "HTTP/1.0"

    # The Python system version, truncated to its first component.
    sys_version = "Python/" + sys.version.split()[0]

    engine = None


    def __init__(self, socket_engine):
        self.engine = socket_engine
        self.passive_sock = None

    def start(self, addr):
        self.passive_sock = self.engine.listen_addr(addr, readable_cb=None, new_conn_cb=self._accept_client, is_blocking=False)

    def stop(self):
        if self.passive_sock:
            self.engine.unlisten(self.passive_sock)

    def handle_GET(self, client):
        raise NotImplementedError

    def handle_HEAD(self, client):
        raise NotImplementedError

    def handle_POST(self, client):
        raise NotImplementedError

    def handle_idle(self, client):
        pass

    def handle_access(self, client):
        """ override this with your logging function, called before sending response"""
        pass

    def handle_closing(self, client):
        """ override this with your logging function, called after sent response"""
        pass

    def handle_error(self, client, e):
        """ override this with your logging function"""
        pass

    def send_response_ex(self, client, code, ok_cb, headers=(), cb_args=(), header_finished=True):
        buf = self._make_response(client, code, None, headers)
        if header_finished:
            buf += "\r\n"
        self.handle_access(client)
        self.engine.write_unblock(client.conn, buf, ok_cb, self._handle_error, (client, ) + cb_args)

    def send_response(self, client, code, headers=()):
        self.send_response_ex(client, code, self._close_client, headers=headers)

    def _send_file(self, conn, client, f):
        buf = None
        try:
            buf = f.read(1024)
        except IOError, e:
            f.close()
            self.handle_error(client, e)
            return
        if buf:
            self.engine.write_unblock  (client.conn, buf, self._send_file, self._handle_error, cb_args=(client, f))
        else:
            f.close()
            self._close_client(conn, client)

    def send_response_file(self, client, f, headers=()):
        self.send_response_ex(client, 200, self._send_file, headers=headers, cb_args=(f,))

    def send_response_content(self, client, mime_type, text, headers=()):
        headers += (('Content-type', mime_type), 
                    ('Content-Length', len(text)),
                    )
        buf = self._make_response(client, 200, None, headers)
        buf += "\r\n"
        buf += text
        self.handle_access(client)
        self.engine.write_unblock(client.conn, buf, self._close_client, self._handle_error, (client, ))

        
    def send_error(self, client, code, msg=None):
        conn = client.conn
        buf = self._make_response(client, code, msg, (
            ('Content-Type', self.error_content_type),
            ('Connection', 'close'),
            ))
        buf += "\r\n"
        if client.command != 'HEAD' and code >= 200 and code not in(204, 304):
            s, explain = self.responses.get(code, ("???", "???"))
            if msg is None:
                msg = s
            content = (self.error_message_format %
                       {'code': code, 'message': _quote_html(msg), 'explain': explain})
            buf += content 

        self.handle_access(client)
        self.engine.write_unblock(conn, buf, self._close_client, self._handle_error, cb_args=(client,))


    def _accept_client(self, sock):
        client = ClientInfo()
        self.engine.put_sock(sock, readable_cb=self._handle_client, readable_cb_args=(client,),
                idle_timeout_cb=self._handle_idle)
        return None

    def _handle_idle(self, conn, client):
        self.handle_idle(client)

    def _handle_client(self, conn, client):
        client.conn = conn
        self.engine.readline_unblock(conn, self.LINE_MAX_LENGTH, self._read_request, None, (client,)) 

    def _handle_error(self, conn, client, *args):
        self.handle_error(client, conn.error)

    def _close_client(self, conn, client, *args):
        self.handle_closing(client)
        if client.close_connection:
            self.engine.close_conn(client.conn)
        else:
            self.engine.watch_conn(client.conn)

    def _read_request(self, conn, client):
        client.close_connection = 1
        line = conn.get_readbuf()
        if line[-2:] == '\r\n':
            line = line[:-2]
        elif line[-1:] == '\n':
            line = line[:-1]
        words = line.split()
        if len(words) == 3:
            [command, path, version] = words
            if version[:5] != 'HTTP/':
                self.send_error(client, 400, "Bad request version(%r)" % version)
                return False
            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except(ValueError, IndexError):
                self.send_error(client, 400, "Bad request version(%r)" % version)
                return False
            if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
                client.close_connection = 0
            if version_number >= (2, 0):
                self.send_error(client, 505,
                          "Invalid HTTP Version(%s)" % base_version_number)
                return False
        elif len(words) == 2:
            [command, path] = words
            client.close_connection = 1
            if command != 'GET':
                self.send_error(client, 400,
                                "Bad HTTP/0.9 request type(%r)" % command)
                return False
        elif not words:
            return False
        else:
            self.send_error(client, 400, "Bad request syntax(%r)" % line)
            return False
        client.command, client.path, client.request_version = command, path, version

        client.headers = []
        self.engine.readline_unblock(conn, self.LINE_MAX_LENGTH, self._read_header, None, (client,))
#        return True

    def _read_header(self, conn, client):
        """ read the rfc 822 msg header """
        line = conn.get_readbuf()
        line = line.strip('\r\n')
        if line == '':
            #process header
            _headers = Rfc822Headers()
            try:
                _headers.unpack(client.headers)
            except InvalidHeader:
                self.send_error(client, 400, "invalid header")
                return
            client.headers = _headers
            self._proc_request(client)
            return
        if line[0] in [' ', '\t']: # continue line
            if len(client.headers) == 0:
                self.send_error(client, 400, "Bad request syntax(%r)" % line)
                return
            client.headers[-1] += line
        else:
            client.headers.append(line)
        self.engine.readline_unblock(conn, self.LINE_MAX_LENGTH, self._read_header, None, (client,))


    def _proc_request(self, client):
        conntype = client.headers.get('Connection', "")
        if conntype.lower() == 'close':
            client.close_connection = 1
        elif(conntype.lower() == 'keep-alive' and
                self.protocol_version >= "HTTP/1.1"):
            client.close_connection = 0

        try:
            if client.command == 'GET':
                self.handle_GET(client)
            elif client.command == 'POST':
                self.handle_POST(client)
            elif client.command == 'HEAD':
                self.handle_HEAD(client)
            else:
                raise NotImplementedError
        except NotImplementedError:
            self.send_error(client, 501, "Unsupported method(%s)" % client.command)


    def _make_response(self, client, code, msg=None, headers=()):
        if msg is None:
            if code in self.responses:
                msg = self.responses[code][0]
            else:
                msg = ''
        buf = ""
        if client.request_version != 'HTTP/0.9':
            buf += "%s %d %s\r\n" % (self.protocol_version, code, msg)
            header = Rfc822Headers()
            header.add_header('Server', self.version_string())
            header.add_header('Date', self.date_time_string())
            for h in headers:
                header.add_header(*h)
            buf += header.pack()
        client.response_code = code
        client.content_length = header.get('Content-Length', '-')
        return buf


    def version_string(self):
        """Return the server software version string."""
        return self.server_version + ' ' + self.sys_version

    def date_time_string(self, timestamp=None):
        """Return the current date and time formatted for a message header."""
        if timestamp is None:
            timestamp = time.time()
        year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
        s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
                self.weekdayname[wd],
                day, self.monthname[month], year,
                hh, mm, ss)
        return s


    # Table mapping response codes to messages; entries have the
    # form {code: (shortmessage, longmessage)}.
    # See RFC 2616.
    responses = {
        100: ('Continue', 'Request received, please continue'),
        101: ('Switching Protocols',
              'Switching to new protocol; obey Upgrade header'),

        200: ('OK', 'Request fulfilled, document follows'),
        201: ('Created', 'Document created, URL follows'),
        202: ('Accepted',
              'Request accepted, processing continues off-line'),
        203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
        204: ('No Content', 'Request fulfilled, nothing follows'),
        205: ('Reset Content', 'Clear input form for further input.'),
        206: ('Partial Content', 'Partial content follows.'),

        300: ('Multiple Choices',
              'Object has several resources -- see URI list'),
        301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
        302: ('Found', 'Object moved temporarily -- see URI list'),
        303: ('See Other', 'Object moved -- see Method and URL list'),
        304: ('Not Modified',
              'Document has not changed since given time'),
        305: ('Use Proxy',
              'You must use proxy specified in Location to access this '
              'resource.'),
        307: ('Temporary Redirect',
              'Object moved temporarily -- see URI list'),

        400: ('Bad Request',
              'Bad request syntax or unsupported method'),
        401: ('Unauthorized',
              'No permission -- see authorization schemes'),
        402: ('Payment Required',
              'No payment -- see charging schemes'),
        403: ('Forbidden',
              'Request forbidden -- authorization will not help'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed',
              'Specified method is invalid for this resource.'),
        406: ('Not Acceptable', 'URI not available in preferred format.'),
        407: ('Proxy Authentication Required', 'You must authenticate with '
              'this proxy before proceeding.'),
        408: ('Request Timeout', 'Request timed out; try again later.'),
        409: ('Conflict', 'Request conflict.'),
        410: ('Gone',
              'URI no longer exists and has been permanently removed.'),
        411: ('Length Required', 'Client must specify Content-Length.'),
        412: ('Precondition Failed', 'Precondition in headers is false.'),
        413: ('Request Entity Too Large', 'Entity is too large.'),
        414: ('Request-URI Too Long', 'URI is too long.'),
        415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
        416: ('Requested Range Not Satisfiable',
              'Cannot satisfy request range.'),
        417: ('Expectation Failed',
              'Expect condition could not be satisfied.'),

        500: ('Internal Server Error', 'Server got itself in trouble'),
        501: ('Not Implemented',
              'Server does not support this operation'),
        502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
        503: ('Service Unavailable',
              'The server cannot process the request due to a high load'),
        504: ('Gateway Timeout',
              'The gateway server did not receive a timely response'),
        505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
        }

    weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    monthname = [None,
                 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']



# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
