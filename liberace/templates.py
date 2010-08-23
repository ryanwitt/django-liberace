apache_conf = """
# Sample apache config for Fabulous django deployment.

NameVirtualHost *:80

<VirtualHost *:80>

    WSGIDaemonProcess %(project_name)s \
        processes=2 threads=5 display-name=%(project_name)s

    #
    # URL mapping
    #
    WSGIScriptAlias / %(conf_path)s/wsgi.py
    Alias /media/ %(media_path)s

    #
    # Filesystem permissions (necessary for above to work)
    #
    <Directory />
        Order deny,allow
        deny from all
    </Directory>
    <Directory %(conf_path)s>
        WSGIProcessGroup %(project_name)s
        Order allow,deny
        allow from all
    </Directory>
    <Directory %(media_path)s>
        Order allow,deny
        allow from all
    </Directory>
    <Directory %(data_path)s>
        Order deny,allow
        deny from all
    </Directory>

</VirtualHost>
"""

wsgi_script = """
import os
import sys

# Add project to our path
sys.path.insert(0, '%(django_project_path)s')

# Activate virtualenv support
activate_this = '%(virtualenv_path)s/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

os.environ['DJANGO_SETTINGS_MODULE'] = '%(django_settings_module)s'
os.environ['PYTHON_EGG_CACHE'] = '%(egg_cache_path)s'

# Preload django environment
settings = __import__(os.environ['DJANGO_SETTINGS_MODULE'])
import django.core.management
django.core.management.setup_environ(settings)
utility = django.core.management.ManagementUtility()
command = utility.fetch_command('runserver')
command.validate()
import django.conf, django.utils
django.utils.translation.activate(django.conf.settings.LANGUAGE_CODE)

# Hand off to django handler
import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
"""


