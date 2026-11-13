#!/usr/bin/env python3
"""Ricostruzione didattica della topologia 1 descritta nell'elaborato (non sorgente originale)."""
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


def main():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch, link=TCLink, autoSetMacs=False)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    h1 = net.addHost('h1', ip='10.0.0.1/8', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/8', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/8', mac='00:00:00:00:00:03')
    s1, s2, s3, s4 = [net.addSwitch('s%d' % i, protocols='OpenFlow13') for i in range(1, 5)]
    net.addLink(h1, s1, port2=1, bw=6, delay='0.0025ms')
    net.addLink(h2, s2, port2=1, bw=6, delay='0.0025ms')
    net.addLink(h3, s4, port2=1, bw=6, delay='0.0025ms')
    net.addLink(s1, s3, port1=3, port2=1, bw=3, delay='25ms')
    net.addLink(s2, s3, port1=2, port2=2, bw=3, delay='25ms')
    net.addLink(s3, s4, port1=3, port2=2, bw=3, delay='25ms')
    try:
        net.start()
        net.pingAll()
        CLI(net)
    finally:
        net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    main()
