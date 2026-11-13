"""Baseline Ryu OpenFlow 1.3 (ricostruzione ispirata all'esempio simple_switch_13)."""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types

class BaselineSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.mac_to_port={}
    def add_flow(self,dp,priority,match,actions):
        p=dp.ofproto_parser
        dp.send_msg(p.OFPFlowMod(datapath=dp,priority=priority,match=match,
            instructions=[p.OFPInstructionActions(dp.ofproto.OFPIT_APPLY_ACTIONS,actions)]))
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures,CONFIG_DISPATCHER)
    def features(self,ev):
        dp=ev.msg.datapath;p=dp.ofproto_parser;o=dp.ofproto
        self.add_flow(dp,0,p.OFPMatch(),[p.OFPActionOutput(o.OFPP_CONTROLLER,o.OFPCML_NO_BUFFER)])
    @set_ev_cls(ofp_event.EventOFPPacketIn,MAIN_DISPATCHER)
    def packet_in(self,ev):
        msg=ev.msg;dp=msg.datapath;p=dp.ofproto_parser;o=dp.ofproto
        port=msg.match['in_port'];pkt=packet.Packet(msg.data)
        eth=pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype==ether_types.ETH_TYPE_LLDP:return
        self.mac_to_port.setdefault(dp.id,{})[eth.src]=port
        out_port=self.mac_to_port[dp.id].get(eth.dst,o.OFPP_FLOOD)
        actions=[p.OFPActionOutput(out_port)]
        if out_port != o.OFPP_FLOOD:
            self.add_flow(dp,1,p.OFPMatch(in_port=port,eth_dst=eth.dst),actions)
        dp.send_msg(p.OFPPacketOut(datapath=dp,buffer_id=o.OFP_NO_BUFFER,
                                  in_port=port,actions=actions,data=msg.data))
