# Limiti, audit e attività future

1. **Riproducibilità parziale**: tre controller originali, quattro file JSON e uno script bash originale sono presenti; le due topologie e la baseline sono **ricostruzioni documentate**, non sorgenti ricevuti.
2. **Ambiente non verificato**: gli script sono stati sottoposti a controllo sintattico, ma non sono stati eseguiti su Mininet/Ryu in una Ubuntu VM in questa consegna.
3. **Dipendenze**: registrare versioni di Mininet, Open vSwitch, Ryu, Python, iperf, Eventlet nella propria VM dopo un test riuscito.
4. **Parsing JSON**: i controller originali usano `eval(key)`, sconsigliato con input non fidato. Una futura versione dovrebbe usare `ast.literal_eval()` e validazione strutturale.
5. **Port blocking**: l'azione drop su `in_port` blocca tutto il traffico su quella porta (potenziale impatto legittimo). Sbloccare installando un flow con `OFPP_NORMAL` non è un ripristino universale del comportamento precedente.
6. **Link blocking**: `host_info_net2_block.json` include interfacce inter-switch con `null`. La funzione `block_port()` dei controller originali usa `attacker_info.get(...)` e può generare `AttributeError` su queste entry. Richiede una revisione esplicita prima di ripetere questo test.
7. **IP blocking**: match `eth_type=0x0800, ipv4_src=...`: colpisce IPv4, non IPv6, e non protegge da spoofing. Il valore `unknown` non è un IP valido per una regola OpenFlow.
8. **Thread e stato**: verificare concorrenza, shutdown, scadenza dei blocchi, contatori che possono azzerarsi e gestione riconnessioni datapath. Assenza di test automatizzati funzionali.
9. **Valutazione scientifica**: grafici e risultati originali derivano dal PDF ma non sono forniti pcap o csv per rianalisi indipendente. Non trascrivere numeri estratti dai grafici senza verificare i dati grezzi.
10. **Proprietà intellettuale**: repository di progetto congiunto. Ottenere consenso del coautore prima di pubblicare e scegliere una licenza condivisa.


## Originali aggiunti nella versione finale
- `controllers/controller_original.py`: errore identificato a riga `parser = datapath.ofproto_parunser`; il file rimane originale.
- `controllers/controller_baseline_fixed.py`: versione di utilizzo in cui è corretto solamente `ofproto_parser`.
- `topologies/topology_original.py`: 2 host, 3 switch; non sostituisce le ricostruzioni degli scenari a 3/4 host.
- `assets/original-report/`: 90 PNG estratti direttamente da DOCX; screenshot storici, non nuove evidenze sperimentali.
