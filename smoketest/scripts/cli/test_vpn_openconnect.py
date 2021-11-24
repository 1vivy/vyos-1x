#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.util import process_named_running

OCSERV_CONF = '/run/ocserv/ocserv.conf'
base_path = ['vpn', 'openconnect']
cert = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
cert_key = '/etc/ssl/private/ssl-cert-snakeoil.key'

class TestVpnOpenconnect(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Delete vpn openconnect configuration
        self.cli_delete(base_path)
        self.cli_commit()

    def test_vpn(self):
        user = 'vyos_user'
        password = 'vyos_pass'
        self.cli_delete(base_path)
        self.cli_set(base_path + ["authentication", "local-users", "username", user, "password", password])
        self.cli_set(base_path + ["authentication", "mode", "local"])
        self.cli_set(base_path + ["network-settings", "client-ip-settings", "subnet", "192.0.2.0/24"])
        self.cli_set(base_path + ["ssl", "ca-cert-file", cert])
        self.cli_set(base_path + ["ssl", "cert-file", cert])
        self.cli_set(base_path + ["ssl", "key-file", cert_key])

        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running('ocserv-main'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
