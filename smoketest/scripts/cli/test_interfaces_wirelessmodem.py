#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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
import unittest

from psutil import process_iter
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError

config_file = '/etc/ppp/peers/{}'
base_path = ['interfaces', 'wirelessmodem']

def get_config_value(interface, key):
    with open(config_file.format(interface), 'r') as f:
        for line in f:
            if line.startswith(key):
                return list(line.split())
    return []

class WWANInterfaceTest(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self._interfaces = ['wlm0', 'wlm1']

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_wwan(self):
        for interface in self._interfaces:
            self.cli_set(base_path + [interface, 'no-peer-dns'])
            self.cli_set(base_path + [interface, 'connect-on-demand'])

            # check validate() - APN must be configure
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(base_path + [interface, 'apn', 'vyos.net'])

            # check validate() - device must be configure
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(base_path + [interface, 'device', 'ttyS0'])

            # commit changes
            self.cli_commit()

        # verify configuration file(s)
        for interface in self._interfaces:
            tmp = get_config_value(interface, 'ifname')[1]
            self.assertTrue(interface in tmp)

            tmp = get_config_value(interface, 'demand')[0]
            self.assertTrue('demand' in tmp)

            tmp = os.path.isfile(f'/etc/ppp/peers/chat.{interface}')
            self.assertTrue(tmp)

            # Check if ppp process is running in the interface in question
            running = False
            for p in process_iter():
                if "pppd" in p.name():
                    if interface in p.cmdline():
                        running = True

            self.assertTrue(running)

if __name__ == '__main__':
    unittest.main(verbosity=2)
