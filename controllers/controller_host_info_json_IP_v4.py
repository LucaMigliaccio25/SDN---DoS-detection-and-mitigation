import threading
import time
import json

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types


class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.stats_interval = 5  # Intervallo per raccogliere le statistiche dei porti (in secondi)
        self.threshold = 2 * (10**6)  # Soglia in bit per secondo (2 Mbps)
        self.alarm = {}
        self.blacklist_ip = set()
        self.entry_ports = {}  # Dizionario per tenere traccia delle porte di ingresso per ogni flusso
        self.block_duration = 10  # Durata del blocco in secondi (prima prova: 5)
        self.prev_stats = {}
        self.host_info = {}  # Dizionario per tenere traccia degli host e delle loro porte e switch
        self.label = set() # Dizionario per le etichette
        self.load_host_info_json("host_info_net2.json")

    def load_host_info_json(self, filepath):
        with open(filepath, 'r') as json_file:
            data = json.load(json_file)
            self.host_info = {eval(key): value for key, value in data.items()}  # per convertire le chiavi da stringhe a tuple

            print("\n--- DEBUG: STAMPA CONTENUTO FILE JSON ---")
            print(self.host_info)
            print("----------------\n")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Installa la regola di flusso per i pacchetti che non corrispondono a nessuna regola (table-miss flow entry)
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        # Memorizza il datapath
        self.datapaths[datapath.id] = datapath
        # Avvia la raccolta delle statistiche dei porti
        self.start_port_stats_collection(datapath)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)

        datapath.send_msg(mod)

    def start_port_stats_collection(self, datapath):
        # Implementa la logica per iniziare la raccolta delle statistiche dei porti
        threading.Thread(target=self.collect_port_stats, args=(datapath,)).start()

    def collect_port_stats(self, datapath):
        while True:
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser

            req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
            datapath.send_msg(req)
            time.sleep(self.stats_interval)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id

        if dpid not in self.datapaths:
            return

        datapath = self.datapaths[dpid]

        for stat in body:
            if stat.port_no == ofproto_v1_3.OFPP_LOCAL:
                continue

            port_no = stat.port_no
            current_rx_bytes = stat.rx_bytes
            current_tx_bytes = stat.tx_bytes

            # accesso alle chiavi mac-ip
            attacker_info = self.host_info.get((datapath.id, port_no), {})
            attacker_ip = attacker_info.get('ip', 'unknown')

            if (dpid, port_no) in self.prev_stats:
                prev_rx_bytes, prev_tx_bytes = self.prev_stats[(dpid, port_no)]
                rx_bytes_diff = current_rx_bytes - prev_rx_bytes
                tx_bytes_diff = current_tx_bytes - prev_tx_bytes

                rx_throughput = (rx_bytes_diff * 8) / self.stats_interval
                tx_throughput = (tx_bytes_diff * 8) / self.stats_interval

                self.prev_stats[(dpid, port_no)] = (current_rx_bytes, current_tx_bytes)

                if rx_throughput > self.threshold:
                    self.alarm[dpid, port_no] = True
                    self.logger.info("-----------SUPERO LA SOGLIA----------")

                    if attacker_ip not in self.blacklist_ip:
                        if (dpid, port_no) not in self.entry_ports:
                            self.logger.info("****** CONTROLLO SE CHIAMARE LA FUNZIONE PER BLOCCARE L'INDIRIZZO IP ******")
                            self.check_and_block_IP(datapath, port_no, attacker_ip)
                            self.entry_ports[(dpid, port_no)] = True
                        else:
                            self.logger.info("****** TRAFFICO INTERMEDIO - POSSIBILE ATTACCO ******")
                    else:
                        self.logger.info("****** INDIRIZZO IP GIÀ BLOCCATO ******")
                        if attacker_ip not in self.label:
                            self.logger.info("AGGIUNTA ALLA LISTA DI LABEL")
                            self.label.add(attacker_ip)
                            print(self.label) # stampa di debug
                else:
                    self.alarm[dpid, port_no] = False
                    self.logger.info("----------NON SUPERO LA SOGLIA-----------")

                    if attacker_ip in self.blacklist_ip:
                        self.blacklist_ip.remove(attacker_ip)
                        if (dpid, port_no) in self.entry_ports:
                            del self.entry_ports[(dpid, port_no)]

                self.logger.info(
                    "IP Address: %s, Rx Throughput: %d bps, Tx Throughput: %d bps, Alarm: %s",
                    attacker_ip, rx_throughput, tx_throughput, self.alarm[dpid, port_no]
                )
                self.logger.info("\n\n")
            else:
                self.prev_stats[(dpid, port_no)] = (current_rx_bytes, current_tx_bytes)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # Ignora i pacchetti LLDP
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # Impara un indirizzo MAC per evitare il flooding la prossima volta
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Installa una regola di flusso per evitare di processare ulteriormente questo pacchetto
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions, msg.buffer_id)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                return
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def check_and_block_IP(self, datapath, port_no, attacker_ip):
        dpid = datapath.id

        if (dpid, port_no) in self.host_info:
            self.logger.info("Traffico generato direttamente dall'host")
            self.logger.info("****** CHIAMO LA FUNZIONE PER BLOCCARE L'INDIRIZZO IP ******")
            self.block_ip(datapath, port_no, self.block_duration, attacker_ip)
            self.blacklist_ip.add(attacker_ip)
        else:
            self.logger.info("Traffico intermedio - possibile attacco")
            if (dpid, port_no) in self.entry_ports:
                del self.entry_ports[(dpid, port_no)]

    def block_ip(self, datapath, port_no, duration, attacker_ip):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # accesso alle chiavi mac-ip
        attacker_info = self.host_info.get((datapath.id, port_no), {})
        attacker_mac = attacker_info.get('mac', 'unknown')
        

        # match per bloccare l'indirizzo IP dell'attaccante
        match = parser.OFPMatch(eth_type=0x0800, ipv4_src=attacker_ip)
        actions = []

        self.add_flow(datapath, 2, match, actions)

        # stampa delle informazioni sulla coppia switch-porta
        self.logger.info("Blocco del traffico dell'indirizzo ip %s con indirizzo MAC %s per %s secondi", attacker_ip, attacker_mac, duration)


        # Avvia un thread per sbloccare l'IP dopo una durata specifica
        threading.Thread(target=self.unblock_port_after_duration, args=(datapath, port_no, attacker_ip, duration)).start()

    def unblock_port_after_duration(self, datapath, port_no, attacker_ip, duration):
        while True:
            time.sleep(duration)

            if attacker_ip not in self.label:
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser

                match = parser.OFPMatch(eth_type=0x0800, ipv4_src=attacker_ip)
                #match = parser.OFPMatch(in_port=port_no)
                actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]

                self.add_flow(datapath, 2, match, actions)

                self.logger.info("Sblocco del traffico dall'IP %s dello switch %s", attacker_ip, datapath.id)

                self.blacklist_ip.discard(attacker_ip)
                if (datapath.id, port_no) in self.entry_ports:
                    del self.entry_ports[(datapath.id, port_no)]
                break
            else:
                self.logger.info("Rimozione dalla lista dell'indirizzo IP %s", attacker_ip)
                self.label.remove(attacker_ip) # rimozione dell'indirizzo IP
                print(self.label) # stampa di debug
