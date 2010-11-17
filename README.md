# Django Liberace

Fabulous django deployment (from git)

Please report bugs at <http://github.com/ryanwitt/django-liberace/issues>

Please ask questions on the mailing list: <http://groups.google.com/group/django-liberace>

![](https://github.com/ryanwitt/django-liberace/raw/master/liberace.png)

## Features

Liberace is a flexible but easy to use deployment
system using fabric, pip and virtualenv. It is suitable 
for newbies to deploy simple sites, or experienced programmers
as a base for more complex fabric deployments.

Liberace deploys django on apache mod_wsgi for now.

    $ fab deploy -H youruser@production.example.com   # deploys master 
    $ fab deploy_index -H youruser@dev1.example.com   # deploys your git index
    $ fab deploy:branchname -H youruser@production.example.com  # deploys a branch

Liberace automatically detects the platform of the 
system being deployed on and picks appropriate install
steps for that system.

    $ fab detect -H youruser@w1.example.com  # called during deploy and other commands

Liberace supports rollback to the previous deployment:

    $ fab rollback -H youruser@w1.example.com

Liberace copies your ssh keys to your servers (and even
creates your key for you if you have not created one).

    $ fab copy_key -H youruser@w1.example.com
    [w1.example.com] Executing task 'copy_key'
    Where is your ssh key? [~/.ssh/id_rsa.pub] 
    [w1.example.com] put: /Users/ryan/.ssh/id_rsa.pub -> 65877f8fd294d6fb1778ab87ca4c54a837f93f19.rsa.pub
    [w1.example.com] run: cat 65877f8fd294d6fb1778ab87ca4c54a837f93f19.rsa.pub >> ~/.ssh/authorized_keys
    [w1.example.com] run: rm 65877f8fd294d6fb1778ab87ca4c54a837f93f19.rsa.pub
    
    Done.
    Disconnecting from w1.example.com... done.

Liberace deploys to a bunch of systems out of the box:

- Ubuntu
- Debian
- OS X (needs work)
- dreamhost (needs work)
- freebsd (needs work)

Liberace can deploy multiple django projects to the same machine as virtual hosts.

Liberace has templated config files.

Liberace does all sorts of cool things that are not documented yet.

Liberace is BSD licensed.

Liberace is generally fabulous.

## Installing

Liberace requires my fork of fabric for the templated
environment dictionary patch. This will be fixed in the future.

    # first, install fabric
    $ pip install https://github.com/ryanwitt/fabric/tarball/0.9    # (or use easy_install)
    
    # now install liberace!
    $ pip install https://github.com/ryanwitt/fabric/django-liberace/master
    
## Project setup

In your fabfile, import liberace to gain access to its default 
commands:

    # -- fabfile.py --
    from liberace import *
    env.project_name = 'example.com'                  # your site name
    env.django_project_dir = 'example_django_project' # the directory with your settings.py
    
    # your own fabric commands go here
    ...

You need a `_conf` directory to hold your apache and wsgi scripts. You also need
some example scripts. Fortunately, Liberace is fabulous and has a command for that:

    $ fab example_config
    created _conf
    created _conf/apache.conf
    created _conf/wsgi.py
    
    Done.

These files are templated, and you can customize them as you see fit.
