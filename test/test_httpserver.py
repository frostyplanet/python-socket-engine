#!/usr/bin/env python

import _env
from lib.async_httphandler import *
from lib.socket_engine import *
import lib.io_poll as iopoll
import os
from StringIO import StringIO
import posixpath
import BaseHTTPServer
import urllib
import cgi
import traceback
from lib.log import * 
import mimetypes
import threading



class HTTPHandler (baseHTTPHandler):
    
    def __init__ (self, engine, logger):
        baseHTTPHandler.__init__ (self, engine)
        self.logger = logger

    def handle_HEAD (self, client):
        self.process (client, is_head=True)

    def handle_GET (self, client):
        self.process (client, is_head=False)

    def handle_access (self, client):
        msg = '%s - "%s %s %s" %s %s' % (client.conn.peer[0], client.command, 
                client.path, client.request_version, 
                client.response_code, client.content_length)
        self.logger.info (msg)


    def handle_error (self, client):
        msg = '%s - "%s %s %s" %s' % (client.conn.peer[0], client.command,
                client.path, client.request_version, 
                client.conn.error)
        self.logger.error (msg)


    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (They should
        probably be diagnosed.)

        """
        # abandon query parameters
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = os.getcwd ()
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

    def process (self, client, is_head=False):
        """Common code for GET and HEAD commands.
        return values: 
            code, msg, headers, file
        """
        path = self.translate_path (client.path)
        f = None
        if os.path.isdir(path):
            if not client.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response (client, 300, headers=(('Location', client.path + "/"),))
                return
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                try:
                    f = self.list_directory (client, path)
                except IOError, e:
                    return self.send_error (client, 401, "No permission to list directory")
                length = f.tell ()
                f.seek (0)
                if is_head:
                    headers = (
                        ('Content-type', 'text/html'),
                        ('Content-Length', str(length)),
                        ) 
                    self.send_response (client, 200, headers)
                else:
                    self.send_response_content (client, "text/html", f.getvalue ())
                f.close ()
                return
        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error (client, 404, "File not found")
            return
        fs = os.fstat(f.fileno())
        size = str(fs[6])
        headers = (
                    ('Content-type', ctype),
                    ('Content-Length', size),
                    ('Last_Modified', self.date_time_string (fs.st_mtime)),
                    )
        if is_head:
            f.close ()
            self.send_response (client, 200, headers)
        else:
            self.send_response_file (client, f, headers)


    def list_directory(self, client, path):
        """Helper to produce a directory listing (absent index.html).

        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().

        """
        list = os.listdir(path)
        list.sort(key=lambda a: a.lower())
        f = StringIO()
        displaypath = cgi.escape(urllib.unquote(client.path))
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Directory listing for %s</title>\n" % displaypath)
        f.write("<body>\n<h2>Directory listing for %s</h2>\n" % displaypath)
        f.write("<hr>\n<ul>\n")
        for name in list:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            f.write('<li><a href="%s">%s</a>\n'
                    % (urllib.quote(linkname), cgi.escape(displayname)))
        f.write("</ul>\n<hr>\n</body>\n</html>\n")
        return f


    def guess_type(self, path):
        """Guess the type of a file.

        Argument is a PATH (a filename).

        Return value is a string of the form type/subtype,
        usable for a MIME Content-type header.

        The default implementation looks the file's extension
        up in the table self.extensions_map, using application/octet-stream
        as a default; however it would be permissible (if
        slow) to look inside the data to make a better guess.

        """

        base, ext = posixpath.splitext(path)
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        else:
            return self.extensions_map['']

    if not mimetypes.inited:
        mimetypes.init() # try to read system mime.types
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

def start_http_server (logger, ip, port):
    engine = TCPSocketEngine (iopoll.EPoll ())
    engine.set_logger (logger)
    engine.set_timeout (idle_timeout=0, rw_timeout=5)
    handler = HTTPHandler (engine, logger)
    handler.start ((ip, port))
    def _run ():
        print "server started"
        while True:
            try:
                engine.poll ()
            except Exception, e:
                traceback.print_exc ()
                os._exit (1)
                return
    _run ()

if __name__ == '__main__':
    
    logger = Log ("main")
    start_http_server (logger, "0.0.0.0", 8088)



# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
