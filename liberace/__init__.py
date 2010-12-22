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
from liberace.systems import system_specific_module, __all__ as systems

#
# Default Settings (you can override in deployment_settings.py)
#

# Local paths
env.release_file = '{release}.tar.gz'
env.conf_dir = '_conf'
env.data_dir = '_data'
env.media_dir = 'media'
env.egg_cache_dir = '_egg_cache'
env.project_data_dir = 'data'
env.virtualenv_dir = '_python_environment'
env.django_project_dir = ''
env.requirements_file = 'requirements.txt'
env.webserver_config_file = '{conf_dir}/apache.conf'
env.webserver_wsgi_file = '{conf_dir}/wsgi.py'

# Remote paths
env.deploy_path = '/usr/local/sites/{project_name}' 

env.current = '{deploy_path}/current'
env.previous = '{deploy_path}/previous'
env.project_data_path = '{deploy_path}/{project_data_dir}'

env.release_path = '{releases_path}/{release}'
env.releases_path = '{deploy_path}/releases'

env.conf_path = '{release_path}/{conf_dir}'
env.data_path = '{release_path}/{data_dir}'
env.media_path = '{release_path}/{media_dir}'
env.requirements_path = '{release_path}/{requirements_file}'

env.egg_cache_path = '{release_path}/{egg_cache_dir}'
env.virtualenv_path = '{release_path}/{virtualenv_dir}'
env.django_project_path = '{release_path}/{django_project_dir}'

env.project_config_symlink = '{webserver_config_dir}/{project_name}.conf'
env.activate = 'source {virtualenv_path}/bin/activate'

# Other stuff
env.django_settings_module = 'settings'
env.git_branch = 'master'

env.webserver_restart_function = sudo
env.webserver_symlink_function = sudo
env.webserver_can_write_media = True

env.include_paths = ''

env.virtualenv_copy_old = True
env.use_index = False
env.use_rsync = True
env.use_south = False

env.copy_db = False
env.copy_data = False

env.deploy_hook = lambda x:x

def _deploy_hook(env):
    pass

def help():
    print __doc__

def example_config():
    """
    Installs the example configuration into your local directory. Don't forget
    to commit it!
    """
    import templates
    if not os.path.exists(env.conf_dir):
        os.mkdir(env.conf_dir)
        print 'created %(conf_dir)s' % env
    filename = os.path.join(env.conf_dir, 'apache.conf')
    file(filename, 'w+').write(templates.apache_conf)
    print 'created %s' % filename
    filename = os.path.join(env.conf_dir, 'wsgi.py')
    file(filename, 'w+').write(templates.wsgi_script)
    print 'created %s' % filename

#
# System specific settings hooks
#

def _system_config():
    require('system')
    system_specific_module(env.system).settings(env)

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

    # Try and identify each system
    systems = []
    import liberace.systems
    for system in liberace.systems:
        try:
            if system_specific_module(system).identify(env):
                systems.append(system)
        except AttributeError:
            print system
            raise
         
    if len(systems) > 1:
        raise ValueError(
            'More than one system identified! %s identifies as %s' % (
                env.host_string,
                ', '.join(systems),
            )
        )
    elif len(systems) == 0:
        raise ValueError('Cannot identify system for host %(host_string)s' % env)
    else:
        env.system = systems[0]

    print '--> %(host_string)s is running %(system)s' % env
    _system_config()

def deploy(branch = env.git_branch):
    """Deploy master/HEAD to a server. Use 'fab deploy:branchname' to deploy a specific branch."""
    require('project_name')
    env.git_branch = branch
    detect()
    _create_release()
    _upload_release()
    _install_requirements()
    _config_webserver()
    _migrate()
    env.deploy_hook(env)
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
    run('mkdir -p ~/.ssh')
    run('cat %(filename)s.rsa.pub >> ~/.ssh/authorized_keys' % locals())
    run('rm %(filename)s.rsa.pub' % locals())

def set_copy_db(sql_file):
    """Copy your database to the webserver. Use fab copy_db:<path/to/db.sql> deploy:<branch> -H user@host"""
    env.copy_db = True
    env.sql_file = sql_file

def set_copy_data(data_path):
    """Copy your /usr/local/sites/<site>/data. use fab copy_data:<path/to/data> deploy:<branch> -H user@host"""
    env.copy_data = True
    env.new_data_path = data_path

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
            'git archive --prefix=%(release)s/ --format=tar %(git_branch)s '
            '%(include_paths)s | gzip > %(release_file)s' % env
        )

# Remote
def _upload_release():

    sudo('mkdir -p %(deploy_path)s' % env)
    sudo('chown %(user)s:%(webserver_user)s %(deploy_path)s' % env)
    sudo('chown %(user)s:%(webserver_user)s %(releases_path)s' % env)
    run('mkdir -p %(releases_path)s' % env)
    run('mkdir -p %(project_data_path)s' % env)

    new_tgz = os.path.join(env.releases_path, env.release_file)

    def normal_upload():
        put(env.release_file, env.releases_path)

    if env.use_rsync:
        # Attempt to use the previous release to shorten upload time
        if fabric.contrib.files.exists(env.previous):
            temp = env.release
            env.release = run('readlink %(previous)s' % env)
            prev_tgz = env.release_file
            env.release = temp
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
    system_specific_module(env.system).install_requirements(env)

    # Call user hook for this system
    #try:
    #globals()['install_requirements_'+env.system](env)
    env['install_requirements_'+env.system](env)
    #except KeyError:
    #    pass

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
    sudo('chown -R %(user)s:%(webserver_user)s %(release_path)s' % env)
    sudo('chmod -R g+r %(release_path)s' % env)  # webserver gets read to everything
    sudo('chmod g+w %(project_data_path)s' % env)   # but can write only to data dir
    if env.webserver_can_write_media:
        with cd(env.release_path):
            run('chmod -R g+w %(media_path)s' % env)

def _migrate():
    with cd(env.release_path):
        run('%(activate)s; cd %(django_project_path)s; python manage.py syncdb --noinput' % env)
        if env.use_south:
            run('%(activate)s; cd %(django_project_path)s python manage.py migrate --noinput' % env)


