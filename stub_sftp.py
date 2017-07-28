import os, socket, paramiko
from paramiko import ServerInterface, SFTPServerInterface, SFTPServer, SFTPAttributes, SFTPHandle, SFTP_OK, AUTH_SUCCESSFUL, OPEN_SUCCEEDED, AUTH_FAILED

HOST = "192.168.0.169"
PORT = 9505

class StubServer (ServerInterface):
    def check_auth_password(self, username, password):
        if (username == 'root') and (password == '123456'):
            return AUTH_SUCCESSFUL
        else:
            return AUTH_FAILED
        
    def check_auth_publickey(self, username, key):
        return AUTH_SUCCESSFUL
        
    def check_channel_request(self, kind, chanid):
        return OPEN_SUCCEEDED

    def get_allowed_auths(self, username):
        return "password,publickey"


class StubSFTPHandle (SFTPHandle):
    def stat(self):
        try:
            return SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def chattr(self, attr):
        try:
            SFTPServer.set_file_attr(self.filename, attr)
            return SFTP_OK
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)


class StubSFTPServer (SFTPServerInterface):
    ROOT = '/'
        
    def _realpath(self, path):
        print "execute _realpath"
        return self.ROOT + self.canonicalize(path)

    def list_folder(self, path):
        print "execute list_folder"
        path = self._realpath(path)
        if path == '//':
            print "enter if"
            out = []
            dirs = {'/usr/local': '/usr/local', 'root': '/root'}
            for fname in dirs:
                print fname
                attr = SFTPAttributes.from_stat(os.stat('.'))
                attr.size = 4096
                attr.uid = 0
                attr.gid = 0
                attr.mode = 040500
                attr.atime = 1500883030
                attr.mtime = 1500604474
                attr.filename = fname
                out.append(attr)
            return out
        else:
            try:
                out = []
                flist = os.listdir(path)
                for fname in flist:
                    attr = SFTPAttributes.from_stat(os.stat(os.path.join(path, fname)))
                    attr.filename = fname
                    out.append(attr)
                print out
                return out
            except OSError as e:
                return SFTPServer.convert_errno(e.errno)

#    def list_folder(self, path):
#        print "execute list_folder"
#        path = self._realpath(path)
#        try:
#            out = [ ]
#            flist = os.listdir(path)
#            for fname in flist:
#                attr = SFTPAttributes.from_stat(os.stat(os.path.join(path, fname)))
#                attr.filename = fname
#                out.append(attr)
#            return out
#        except OSError as e:
#            return SFTPServer.convert_errno(e.errno)

    def stat(self, path):
        print "execute stat"
        path = self._realpath(path)
        try:
            return SFTPAttributes.from_stat(os.stat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def lstat(self, path):
        print "execute lstat"
        path = self._realpath(path)
        try:
            return SFTPAttributes.from_stat(os.lstat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def open(self, path, flags, attr):
        path = self._realpath(path)
        try:
            binary_flag = getattr(os, 'O_BINARY',  0)
            flags |= binary_flag
            mode = getattr(attr, 'st_mode', None)
            if mode is not None:
                fd = os.open(path, flags, mode)
            else:
                # os.open() defaults to 0777 which is
                # an odd default mode for files
                fd = os.open(path, flags, 0o666)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        if (flags & os.O_CREAT) and (attr is not None):
            attr._flags &= ~attr.FLAG_PERMISSIONS
            SFTPServer.set_file_attr(path, attr)
        if flags & os.O_WRONLY:
            if flags & os.O_APPEND:
                fstr = 'ab'
            else:
                fstr = 'wb'
        elif flags & os.O_RDWR:
            if flags & os.O_APPEND:
                fstr = 'a+b'
            else:
                fstr = 'r+b'
        else:
            # O_RDONLY (== 0)
            fstr = 'rb'
        try:
            f = os.fdopen(fd, fstr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        fobj = StubSFTPHandle(flags)
        fobj.filename = path
        fobj.readfile = f
        fobj.writefile = f
        return fobj

    def remove(self, path):
        path = self._realpath(path)
        try:
            os.remove(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rename(self, oldpath, newpath):
        oldpath = self._realpath(oldpath)
        newpath = self._realpath(newpath)
        try:
            os.rename(oldpath, newpath)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def mkdir(self, path, attr):
        path = self._realpath(path)
        try:
            os.mkdir(path)
            if attr is not None:
                SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rmdir(self, path):
        path = self._realpath(path)
        try:
            os.rmdir(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def chattr(self, path, attr):
        path = self._realpath(path)
        try:
            SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def symlink(self, target_path, path):
        path = self._realpath(path)
        if (len(target_path) > 0) and (target_path[0] == '/'):
            # absolute symlink
            target_path = os.path.join(self.ROOT, target_path[1:])
            if target_path[:2] == '//':
                # bug in os.path.join
                target_path = target_path[1:]
        else:
            # compute relative to path
            abspath = os.path.join(os.path.dirname(path), target_path)
            if abspath[:len(self.ROOT)] != self.ROOT:
                # this symlink isn't going to work anyway -- just break it immediately
                target_path = '<error>'
        try:
            os.symlink(target_path, path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def readlink(self, path):
        path = self._realpath(path)
        try:
            symlink = os.readlink(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        # if it's absolute, remove the root
        if os.path.isabs(symlink):
            if symlink[:len(self.ROOT)] == self.ROOT:
                symlink = symlink[len(self.ROOT):]
                if (len(symlink) == 0) or (symlink[0] != '/'):
                    symlink = '/' + symlink
            else:
                symlink = '<error>'
        return symlink

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    key = paramiko.RSAKey.generate(1024)

    while True:
        conn, addr = server_socket.accept()
        transport = paramiko.Transport(conn)
        transport.add_server_key(key)
        transport.set_subsystem_handler('sftp', paramiko.SFTPServer, StubSFTPServer)
        server = StubServer()
        transport.start_server(server=server)
        channel = transport.accept()

if __name__ == '__main__':
    start_server()