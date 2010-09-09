from fabric.api import *

def identify(env):
    return 'dreamhost' in env.host_string.lower()

def settings(env):
    env.project_deploy_dir = '/home/{user}/sites/{project_name}'
    env.webserver_config_dir = env.project_deploy_dir
    env.webserver_restart_function = run
    env.webserver_symlink_function = run
    env.webserver_user = '{user}'
    #env.webserver_restart_cmd = \
    #            'touch %s' % os.path.join(env.deploy_path, 'restart.txt')

def install_requirements(env):
    run('pip install virtualenv')
    
