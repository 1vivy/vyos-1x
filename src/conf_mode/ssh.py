#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_vrf
from vyos.util import call
from vyos.template import render
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/sshd/sshd_config'
systemd_override = r'/etc/systemd/system/ssh.service.d/override.conf'

sshguard_config_file = '/etc/sshguard/sshguard.conf'
sshguard_whitelist = '/etc/sshguard/whitelist'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ssh']
    if not conf.exists(base):
        return None

    ssh = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    ssh = dict_merge(default_values, ssh)
    # pass config file path - used in override template
    ssh['config_file'] = config_file

    # Ignore default XML values if config doesn't exists
    # Delete key from dict
    if not conf.exists(base + ['dynamic-protection']):
         del ssh['dynamic_protection']

    return ssh

def verify(ssh):
    if not ssh:
        return None

    verify_vrf(ssh)
    return None

def generate(ssh):
    if not ssh:
        if os.path.isfile(config_file):
            os.unlink(config_file)
        if os.path.isfile(systemd_override):
            os.unlink(systemd_override)

        return None

    render(config_file, 'ssh/sshd_config.tmpl', ssh)
    render(systemd_override, 'ssh/override.conf.tmpl', ssh)
    if 'dynamic_protection' in ssh:
        render(sshguard_config_file, 'ssh/sshguard_config.tmpl', ssh)
        render(sshguard_whitelist, 'ssh/sshguard_whitelist.tmpl', ssh)
    # Reload systemd manager configuration
    call('systemctl daemon-reload')

    return None

def apply(ssh):
    systemd_service_sshguard = 'sshguard.service'
    if not ssh:
        # SSH access is removed in the commit
        call('systemctl stop ssh.service')
        call(f'systemctl stop {systemd_service_sshguard}')
        return None

    if 'dynamic_protection' not in ssh:
        call(f'systemctl stop {systemd_service_sshguard}')
    else:
        call(f'systemctl reload-or-restart {systemd_service_sshguard}')

    call('systemctl restart ssh.service')
    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
