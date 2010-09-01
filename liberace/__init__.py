#!/usr/bin/env python
"""
Fabulous django deployment. Now with system detection.

Deploys using the following directory structure (in /var/sites by default)
project_name/
         data/      # for local persistent files
         releases/  # all releases untarred here
         current -> releases/RELEASE
         previous -> ...

Inspired by http://github.com/fiee/generic_django_project/raw/master/fabfile.py
which in-turn is inspired by: 
http://morethanseven.net/2009/07/27/fabric-django-git-apache-mod_wsgi-virtualenv-and-p/
"""
from __future__ import with_statement # python 2.5
from fabric.api import *
import fabric.contrib
import time
import os
import tempfile

#
# Default Settings (you can override in deployment_settings.py)
#
env.release_file_format = '%(release)s.tar.gz'
env.project_deploy_dir = '/usr/local/sites/%(project_name)s' 

env.conf_dir = '_conf'
env.data_dir = '_data'
env.media_dir = 'media'
env.egg_cache_dir = '_egg_cache'
env.project_data_dir = 'data'
env.virtualenv_dir = '_python_environment'

env.django_project_dir = ''
env.django_settings_module = 'settings'
env.requirements_file = 'requirements.txt'

env.webserver_restart_function = sudo
env.webserver_symlink_function = sudo
env.webserver_can_write_media = True

env.include_paths = ''

env.virtualenv_copy_old = True
env.use_index = False
env.use_rsync = True
env.use_south = False

def _deploy_hook(env):
    pass

def help():
    print __doc__

#
# System specific settings hooks
#
def _dreamhost_settings():
    env.project_deploy_dir = '/home/%(user)s/sites/%(project_name)s' % env
    env.webserver_config_dir = env.project_deploy_dir
    env.webserver_restart_function = run
    env.webserver_symlink_function = run
    env.webserver_user = '%(user)s' % env
    #env.webserver_restart_cmd = \
    #            'touch %s' % os.path.join(env.deploy_path, 'restart.txt')

def _dreamhost_install_requirements():
    run('pip install virtualenv')

def _ubuntu_settings():
    env.webserver_config_dir = '/etc/apache2/sites-enabled/'
    env.webserver_restart_cmd = '/etc/init.d/apache2 restart'
    env.webserver_user = 'www-data'

def _ubuntu_install_requirements():
    sudo('apt-get -y install apache2 libapache2-mod-wsgi')
    sudo('apt-get -y install libmysqlclient-dev')
    sudo('apt-get -y install python-dev python-setuptools python-pip')
    sudo('pip install virtualenv')

_debian_settings = _ubuntu_settings
_debian_install_requirements = _ubuntu_install_requirements

def _freebsd_settings():
    env.shell = '/bin/sh -c'
    env.webserver_config_dir = '/usr/local/etc/apache22/Includes/'
    env.webserver_restart_cmd = '/usr/local/etc/rc.d/apache22 restart'
    env.webserver_user = 'www'

def _osx_settings():
    env.webserver_config_dir = '/etc/apache2/other/'
    env.webserver_restart_cmd = 'apachectl restart'
    env.webserver_user = '_www'

def _osx_install_requirements():
    run('pip install virtualenv')

def _system_config():

    # Call system specific setup function from above
    try:
        globals()['_%(system)s_settings' % env]()
    except KeyError:
        pass

    env.deploy_path = env.project_deploy_dir % env
    env.current = os.path.join(env.deploy_path, 'current')
    env.previous = os.path.join(env.deploy_path, 'previous')
    env.releases_path = os.path.join(env.deploy_path, 'releases')
    env.project_data_path = os.path.join(env.deploy_path, env.project_data_dir)

    env.webserver_config_file = '%(conf_dir)s/apache.conf' % env
    env.webserver_wsgi_file = '%(conf_dir)s/wsgi.py' % env

#
# Actions
#
def detect():
    """Detect the system type of a remote host."""
    require('host')

    if 'system' in env:
        del env['system']

    # Start with uname and work from there
    with settings(shell='/bin/sh -c'):
        env.uname = run('uname -a')

    if 'dreamhost' in env.host_string:
        env.system = 'dreamhost'
    elif 'linux' in env.uname.lower():
        with settings(warn_only=True):
            lsb = run('lsb_release -d').lower()
            if 'ubuntu' in lsb:
                env.system = 'ubuntu'
            elif 'debian' in lsb:
                env.system = 'debian'
    elif 'freebsd' in env.uname.lower():
        env.system = 'freebsd'
    elif 'darwin' in env.uname.lower():
        env.system = 'osx'
    print '--> %(host_string)s is running %(system)s' % env
    _system_config()

def deploy():
    """Deploy master/HEAD to a server."""
    require('project_name')
    detect()
    _create_release()
    _upload_release()
    _install_requirements()
    _config_webserver()
    _migrate()
    _deploy_hook(env)
    _symlink_release()
    restart()

def deploy_index():
    """Deploy from your index, not master/HEAD."""
    env.use_index = True
    deploy()

def rollback():
    """Rollback to previous version of code."""
    detect()
    with cd(env.deploy_path):
        run('mv current _swap; mv previous current; mv _swap previous;')
    restart()    

def restart():
    """Restart the webserver. (deploy/rollback call this for you)"""
    detect()
    if 'dreamhost' == env.system:
        run(env.webserver_restart_cmd)
    else:
        sudo(env.webserver_restart_cmd)

def copy_key():
    """Copy your public key to a remote server."""
    default = None
    for default_file in (
        '~/.ssh/id_rsa.pub',
        '~/.ssh/id_dsa.pub',
    ):
        if os.path.exists(os.path.expanduser(default_file)):
            default = default_file
            break
    if not default and fabric.contrib.console.confirm(
        'Can\'t seem to find your ssh key. Create one?'):
        local('ssh-keygen -t rsa')
    prompt(
        'Where is your ssh key?', 
        key = 'ssh_keyfile', 
        default = default,
    )
    import hashlib
    filename = hashlib.sha1(file(os.path.expanduser(
        env.ssh_keyfile)).read()).hexdigest()
    put(env.ssh_keyfile, '%(filename)s.rsa.pub' % locals())
    run('cat %(filename)s.rsa.pub >> ~/.ssh/authorized_keys' % locals())
    run('rm %(filename)s.rsa.pub' % locals())

#
# Subroutines
#

# Local
@runs_once
def _create_release(name=None):
    if name:
        env.release = name
    # Auto-create a release name if not given
    if 'release' not in env:
        env.release = time.strftime('%Y-%m-%d.%H%M%S')

    env.release_file = env.release_file_format % env
    env.release_path = os.path.join(env.releases_path, env.release)

    # Finish config, now that we know where everything is
    env.conf_path = os.path.join(env.release_path, env.conf_dir)
    env.data_path = os.path.join(env.release_path, env.data_dir)
    env.media_path = os.path.join(env.release_path, env.media_dir)

    env.egg_cache_path = os.path.join(env.release_path, env.egg_cache_dir)
    env.virtualenv_path = os.path.join(env.release_path, env.virtualenv_dir)
    env.django_project_path = os.path.join(env.release_path, env.django_project_dir)

    env.project_config_symlink = os.path.join(
        env.webserver_config_dir, '%(project_name)s.conf' % env)
    env.activate = 'source %(virtualenv_path)s/bin/activate' % env

    # Export files from the index
    if env.use_index:
        release = env.release
        tempdir = tempfile.mkdtemp()
        release_dir = os.path.join(tempdir, release)
        local('mkdir -p %(release_dir)s' % locals())
        paths = '-a'#'-- %(include_paths)s' % env if env.include_paths else '-a'
        release_file = env.release_file
        local('git checkout-index --prefix=%(release_dir)s/ %(paths)s'%locals())
        local('tar -czvf %(release_file)s -C %(tempdir)s %(release)s'%locals())
        local('rm -rf %(tempdir)s' % locals())

    # Otherwise do a Normal git export of master/HEAD
    else:
        local(
            'git archive --prefix=%(release)s/ --format=tar master '
            '%(include_paths)s | gzip > %(release_file)s' % env
        )

# Remote
def _upload_release():

    sudo('mkdir -p %(deploy_path)s' % env)
    sudo('chown %(user)s:%(webserver_user)s %(deploy_path)s' % env)
    run('mkdir -p %(releases_path)s' % env)
    run('mkdir -p %(project_data_path)s' % env)

    new_tgz = os.path.join(env.releases_path, env.release_file)

    def normal_upload():
        put(env.release_file, env.releases_path)

    if env.use_rsync:
        # Attempt to use the previous release to shorten upload time
        if fabric.contrib.files.exists(env.previous):
            prev = run('readlink %(previous)s' % env)
            prev_tgz = env.release_file_format % {'release': prev}
            print prev_tgz
            if fabric.contrib.files.exists(prev_tgz):
                run('cp %(prev_tgz)s %(new_tgz)s' % locals())
                fabric.contrib.project.rsync_project(new_tgz, env.release_file)
            else:
                normal_upload()
        else:
            normal_upload()
    else:
        normal_upload()

    with cd(env.releases_path):
        run('tar zxf %(release_file)s' % env)
        #run('rm %(release_file)s' % env)

def _symlink_release():
    with cd(env.deploy_path):
        run('rm -f previous && if [ -e current ]; then mv current previous; fi')
        run('ln -sf %s current' % os.path.join(env.releases_path, env.release))

        # Symlink into the webserver's config space
        config = os.path.join(env.release_path, env.webserver_config_file)
        symlink = env.project_config_symlink
        env.webserver_symlink_function('rm -f %(symlink)s' % locals())
        env.webserver_symlink_function('ln -sf %(config)s %(symlink)s' % locals())

def _install_requirements():

    # Bootstrap with system specific way of installing pip and virtualenv
    try:
        globals()['_%(system)s_install_requirements' % env]()
    except KeyError:
        pass

    # Copy over previous environment if asked
    if env.virtualenv_copy_old:
        oldenv = os.path.join(env.current, env.virtualenv_dir)
        with cd(env.release_path):
            run('if [ -e %(oldenv)s ]; then cp -r %(oldenv)s .; fi' % locals())

    # Now create or update virtualenv and everything else
    with cd(env.release_path):
        run('virtualenv --no-site-packages %(virtualenv_dir)s' % env)
        ## We need to bootstrap into pip to avoid problems with old versions
        #run('%(activate)s; pip install pip==0.7.2' % env)
        run('%(activate)s; pip install -r %(requirements_file)s' % env)


def _evaluate_and_push_file(local_filename):

    # Create local temporary file and evaluate template
    fd, tmp_filename = tempfile.mkstemp(dir='.', suffix='.conf')
    tmp, conf = os.fdopen(fd, 'w+'), file(local_filename, 'r')
    tmp.write(conf.read() % env)
    tmp.close()
    conf.close()

    # Push evaluated template to server (replacing existing file)
    put(tmp_filename, env.deploy_path)
    tmp_remote = os.path.basename(tmp_filename)
    local_remote = os.path.join(env.current, local_filename)
    with cd(env.deploy_path):
        run('mv %(tmp_remote)s %(local_remote)s' % locals())

    local('rm -f %(tmp_filename)s' % locals())

def _config_webserver():
    print 'Generating config file'
    #_evaluate_and_push_file(env.webserver_config_file)
    #_evaluate_and_push_file(env.webserver_wsgi_file)

    fabric.contrib.files.upload_template(
        env.webserver_config_file, 
        os.path.join(env.release_path, env.webserver_config_file), 
        context = env,
    )
    fabric.contrib.files.upload_template(
        env.webserver_wsgi_file, 
        os.path.join(env.release_path, env.webserver_wsgi_file), 
        context = env,
    )

    # Create egg cache and set permissions
    run('mkdir -p %(egg_cache_path)s' % env)
    run('chmod g+w %(egg_cache_path)s' % env)

    # Get permissions right
    sudo('chown -R %(user)s:%(webserver_user)s %(deploy_path)s' % env)
    run('chmod -R g+r %(deploy_path)s' % env) # webserver gets read to everything
    run('chmod -R g+w %(project_data_path)s' % env)   # but can write only to data dir
    if env.webserver_can_write_media:
        with cd(env.release_path):
            run('chmod -R g+w %(media_path)s' % env)

def _migrate():
    with cd(env.release_path):
        run('%(activate)s; cd %(django_project_path)s; python manage.py syncdb --noinput' % env)
        if env.use_south:
            run('%(activate)s; cd %(django_project_path)s python manage.py migrate' % env)

#
# Import deployment settings
#
try:
    import inspect
    import deployment_settings
    env.update(dict(
        (k, v) for k,v in
        inspect.getmembers(deployment_settings)
        if not k.startswith('_')
    ))
except ImportError:
    pass

