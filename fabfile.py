
#from fabric.api import *
from liberace import *

env.root = '~/ryan'
env.fullpath = '{root}/file.txt'

def test():
    local('echo "path is %(fullpath)s"' % env)
