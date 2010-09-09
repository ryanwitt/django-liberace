from fabric.api import *

def identify(env):
    return 'darwin' in env.uname.lower()

def settings(env):
    env.webserver_config_dir = '/etc/apache2/other/'
    env.webserver_restart_cmd = 'apachectl restart'
    env.webserver_user = '_www'

def install_requirements(env):
    run('pip install virtualenv')

