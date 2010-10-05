"""
Sub-package containing one module per system (ubuntu, osx, etc.)
that sets up system specific commands and environment variables.

Modules in this package should contain the following functions:

.. function:: identify(env)

   Hook to identify this system. *env* should already contain
   a variable called *uname* which you can use to do an initial
   check. Call other commands as necessary and return *True* if
   you positively identify this machine as your system. It's an
   error for a machien to identify as two types of system, so
   code accordingly. Ex::

     def identify(env):
         if 'linux' in env.uname.lower():
             with settings(warn_only=True):
                 env.lsb_release = env.lsb_release or run('lsb_release -d').lower()
                 if 'ubuntu' in env.lsb_release:
                     return True

.. function:: settings(env)

   Overrides default environment and adds new environment
   items for a given system. Ex::

     def settings(env):
         env.webserver_config_dir = '/etc/apache2/sites-enabled/'
         env.webserver_restart_cmd = '/etc/init.d/apache2 restart'
         env.webserver_user = 'www-data'

.. function:: install_requirements(env)

   This function should use standard fabric api commands to 
   install all the requirements needed to run the app on the
   given system. This should include things like the webserver,
   database drivers, python, pip and virtualenv. *env* is the
   fabric environment. Ex::

     from fabric.api import *
     def install_requirements(env):
        sudo('apt-get -y install apache2 libapache2-mod-wsgi')        
        sudo('apt-get -y install libmysqlclient-dev')                 
        sudo('apt-get -y install python-dev python-setuptools python-p
    ip')                                                              
        sudo('pip install virtualenv')                                
"""

__all__ = (
    'ubuntu',
    'debian',
    'osx',
    'freebsd',
    'dreamhost',
)

def system_specific_module(system):
    """Returns the module for the given system."""
    return __import__('liberace.systems.'+system, fromlist=[system])

