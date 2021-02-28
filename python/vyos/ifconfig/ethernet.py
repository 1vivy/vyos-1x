# Copyright 2019-2021 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os
import re

from vyos.ifconfig.interface import Interface
from vyos.util import run
from vyos.util import dict_search
from vyos.validate import assert_list

@Interface.register
class EthernetIf(Interface):
    """
    Abstraction of a Linux Ethernet Interface
    """

    default = {
        'type': 'ethernet',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'ethernet',
            'prefixes': ['lan', 'eth', 'eno', 'ens', 'enp', 'enx'],
            'bondable': True,
            'broadcast': True,
            'bridgeable': True,
            'eternal': '(lan|eth|eno|ens|enp|enx)[0-9]+$',
        }
    }

    @staticmethod
    def feature(ifname, option, value):
        run(f'ethtool -K {ifname} {option} {value}','ifconfig')
        return False

    _command_set = {**Interface._command_set, **{
        'gro': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'gro', v),
            # 'shellcmd': 'ethtool -K {ifname} gro {value}',
        },
        'gso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'gso', v),
            # 'shellcmd': 'ethtool -K {ifname} gso {value}',
        },
        'sg': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'sg', v),
            # 'shellcmd': 'ethtool -K {ifname} sg {value}',
        },
        'tso': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'tso', v),
            # 'shellcmd': 'ethtool -K {ifname} tso {value}',
        },
        'ufo': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'possible': lambda i, v: EthernetIf.feature(i, 'ufo', v),
            # 'shellcmd': 'ethtool -K {ifname} ufo {value}',
        },
    }}

    _sysfs_set = {**Interface._sysfs_set, **{
        'rps': {
            'convert': lambda cpus: cpus if cpus else '0',
            'location': '/sys/class/net/{ifname}/queues/rx-0/rps_cpus',
        },
    }}

    def get_driver_name(self):
        """
        Return the driver name used by NIC. Some NICs don't support all
        features e.g. changing link-speed, duplex

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.get_driver_name()
        'vmxnet3'
        """
        ifname = self.config['ifname']
        sysfs_file = f'/sys/class/net/{ifname}/device/driver/module'
        if os.path.exists(sysfs_file):
            link = os.readlink(sysfs_file)
            return os.path.basename(link)
        else:
            return None

    def set_flow_control(self, enable):
        """
        Changes the pause parameters of the specified Ethernet device.

        @param enable: true -> enable pause frames, false -> disable pause frames

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_flow_control(True)
        """
        ifname = self.config['ifname']

        if enable not in ['on', 'off']:
            raise ValueError("Value out of range")

        driver_name = self.get_driver_name()
        if driver_name in ['vmxnet3', 'virtio_net', 'xen_netfront']:
            self._debug_msg(f'{driver_name} driver does not support changing '\
                            'flow control settings!')
            return

        # Get current flow control settings:
        cmd = f'ethtool --show-pause {ifname}'
        output, code = self._popen(cmd)
        if code == 76:
            # the interface does not support it
            return ''
        if code:
            # never fail here as it prevent vyos to boot
            print(f'unexpected return code {code} from {cmd}')
            return ''

        # The above command returns - with tabs:
        #
        # Pause parameters for eth0:
        # Autonegotiate:  on
        # RX:             off
        # TX:             off
        if re.search("Autonegotiate:\ton", output):
            if enable == "on":
                # flowcontrol is already enabled - no need to re-enable it again
                # this will prevent the interface from flapping as applying the
                # flow-control settings will take the interface down and bring
                # it back up every time.
                return ''

        # Assemble command executed on system. Unfortunately there is no way
        # to change this setting via sysfs
        cmd = f'ethtool --pause {ifname} autoneg {enable} tx {enable} rx {enable}'
        output, code = self._popen(cmd)
        if code:
            print(f'could not set flowcontrol for {ifname}')
        return output

    def set_speed_duplex(self, speed, duplex):
        """
        Set link speed in Mbit/s and duplex.

        @speed can be any link speed in MBit/s, e.g. 10, 100, 1000 auto
        @duplex can be half, full, auto

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_speed_duplex('auto', 'auto')
        """

        if speed not in ['auto', '10', '100', '1000', '2500', '5000', '10000',
                         '25000', '40000', '50000', '100000', '400000']:
            raise ValueError("Value out of range (speed)")

        if duplex not in ['auto', 'full', 'half']:
            raise ValueError("Value out of range (duplex)")

        driver_name = self.get_driver_name()
        if driver_name in ['vmxnet3', 'virtio_net', 'xen_netfront']:
            self._debug_msg(f'{driver_name} driver does not support changing '\
                            'speed/duplex settings!')
            return

        # Get current speed and duplex settings:
        ifname = self.config['ifname']
        cmd = f'ethtool {ifname}'
        tmp = self._cmd(cmd)

        if re.search("\tAuto-negotiation: on", tmp):
            if speed == 'auto' and duplex == 'auto':
                # bail out early as nothing is to change
                return
        else:
            # read in current speed and duplex settings
            cur_speed = 0
            cur_duplex = ''
            for line in tmp.splitlines():
                if line.lstrip().startswith("Speed:"):
                    non_decimal = re.compile(r'[^\d.]+')
                    cur_speed = non_decimal.sub('', line)
                    continue

                if line.lstrip().startswith("Duplex:"):
                    cur_duplex = line.split()[-1].lower()
                    break

            if (cur_speed == speed) and (cur_duplex == duplex):
                # bail out early as nothing is to change
                return

        cmd = f'ethtool -s {ifname}'
        if speed == 'auto' or duplex == 'auto':
            cmd += ' autoneg on'
        else:
            cmd += f' speed {speed} duplex {duplex} autoneg off'
        return self._cmd(cmd)

    def set_gro(self, state):
        """
        Enable Generic Receive Offload. State can be either True or False.

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_gro(True)
        """
        if not isinstance(state, bool):
            raise ValueError("Value out of range")
        return self.set_interface('gro', 'on' if state else 'off')

    def set_gso(self, state):
        """
        Enable Generic Segmentation offload. State can be either True or False.
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_gso(True)
        """
        if not isinstance(state, bool):
            raise ValueError("Value out of range")
        return self.set_interface('gso', 'on' if state else 'off')

    def set_rps(self, state):
        if not isinstance(state, bool):
            raise ValueError("Value out of range")

        rps_cpus = '0'
        if state:
            # Enable RPS on all available CPUs except CPU0 which we will not
            # utilize so the system has one spare core when it's under high
            # preasure to server other means. Linux sysfs excepts a bitmask
            # representation of the CPUs which should participate on RPS, we
            # can enable more CPUs that are physically present on the system,
            # Linux will clip that internally!
            rps_cpus = 'ffffffff,ffffffff,ffffffff,fffffffe'

        # send bitmask representation as hex string without leading '0x'
        return self.set_interface('rps', rps_cpus)

    def set_sg(self, state):
        """
        Enable Scatter-Gather support. State can be either True or False.

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_sg(True)
        """
        if not isinstance(state, bool):
            raise ValueError("Value out of range")
        return self.set_interface('sg', 'on' if state else 'off')

    def set_tso(self, state):
        """
        Enable TCP segmentation offloading. State can be either True or False.

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_tso(False)
        """
        if not isinstance(state, bool):
            raise ValueError("Value out of range")
        return self.set_interface('tso', 'on' if state else 'off')

    def set_ufo(self, state):
        """
        Enable UDP fragmentation offloading. State can be either True or False.

        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_udp_offload(True)
        """
        if not isinstance(state, bool):
            raise ValueError("Value out of range")
        return self.set_interface('ufo', 'on' if state else 'off')

    def set_ring_buffer(self, b_type, b_size):
        """
        Example:
        >>> from vyos.ifconfig import EthernetIf
        >>> i = EthernetIf('eth0')
        >>> i.set_ring_buffer('rx', '4096')
        """
        ifname = self.config['ifname']
        cmd = f'ethtool -G {ifname} {b_type} {b_size}'
        output, code = self._popen(cmd)
        # ethtool error codes:
        #  80 - value already setted
        #  81 - does not possible to set value
        if code and code != 80:
            print(f'could not set "{b_type}" ring-buffer for {ifname}')
        return output


    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # disable ethernet flow control (pause frames)
        value = 'off' if 'disable_flow_control' in config else 'on'
        self.set_flow_control(value)

        # GRO (generic receive offload)
        self.set_gro(dict_search('offload.gro', config) != None)

        # GSO (generic segmentation offload)
        self.set_gso(dict_search('offload.gso', config) != None)

        # RPS - Receive Packet Steering
        self.set_rps(dict_search('offload.rps', config) != None)

        # scatter-gather option
        self.set_sg(dict_search('offload.sg', config) != None)

        # TSO (TCP segmentation offloading)
        self.set_tso(dict_search('offload.tso', config) != None)

        # UDP fragmentation offloading
        self.set_ufo(dict_search('offload.ufo', config) != None)

        # Set physical interface speed and duplex
        if {'speed', 'duplex'} <= set(config):
            speed = config.get('speed')
            duplex = config.get('duplex')
            self.set_speed_duplex(speed, duplex)

        # Set interface ring buffer
        if 'ring_buffer' in config:
            for b_type in config['ring_buffer']:
                self.set_ring_buffer(b_type, config['ring_buffer'][b_type])

        # call base class first
        super().update(config)
