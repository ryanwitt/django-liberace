from fabric.api import *

def identify(env):
    if 'linux' in env.uname.lower():
        with settings(warn_only=True):
            env.lsb_release = env.lsb_release or run('lsb_release -d').lower()
            if 'debian' in env.lsb_release:
                return True

def settings(env):
    env.webserver_config_dir = '/etc/apache2/sites-enabled/'
    env.webserver_restart_cmd = '/etc/init.d/apache2 restart'
    env.webserver_user = 'www-data'

def install_requirements(env):
    raise NotImplementedError()
    
