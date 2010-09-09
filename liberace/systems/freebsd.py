from fabric.api import *

def identify(env):
    return 'freebse' in env.uname.lower()

def settings(env):
    env.shell = '/bin/sh -c'
    env.webserver_config_dir = '/usr/local/etc/apache22/Includes/'
    env.webserver_restart_cmd = '/usr/local/etc/rc.d/apache22 restart'
    env.webserver_user = 'www'

def install_requirements(env):
    raise NotImplementedError()
    
