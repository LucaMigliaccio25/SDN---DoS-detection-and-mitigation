# Riproduzione degli esperimenti (Ubuntu 22.04)

> **Stato:** procedura ricostruita dalla relazione e dai sorgenti forniti; non verificata tramite un'esecuzione end-to-end in una VM Ubuntu 22.04. Il file `topology_original.py` è originale ma descrive 2 host/3 switch, non gli scenari della relazione. `topology_1.py` e `topology_2.py` sono ricostruzioni dalla relazione. Il baseline originale presenta un typo (`ofproto_parunser`): `controller_baseline_fixed.py` lo corregge senza alterare il file sorgente.

## 1. VM e dipendenze

- Ubuntu 22.04 (nell'elaborato: VirtualBox); usare una VM isolata e una rete di laboratorio.
- Mininet, Open vSwitch, Ryu (Python), iperf **2**, tcpdump/Wireshark, xterm (se si desidera UI); nel documento sono citati anche D-ITG e nload.

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv mininet openvswitch-switch iperf tcpdump wireshark xterm nload d-itg
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install 'ryu==4.34'
```

**Compatibilità:** Ryu 4.34 ha dipendenze storiche; con Python 3.10/moderni pacchetti pip potrebbe fallire l'avvio per incompatibilità (ad es. eventlet). Non forniamo una combinazione di versioni verificata. Se necessario, fissare le versioni dopo aver provato il setup nella VM e documentarle in una release. Verificare `ryu-manager --version`, `mn --version`, `ovs-vsctl --version`, `iperf -v`. `ryu-manager` può essere disponibile solo dentro il virtualenv.

## 2. Avvio del controller e della topologia

Dalla **radice del repository** (importante per la lettura del file JSON):

```bash
# Terminale 1: baseline, senza mitigazione
ryu-manager --ofp-tcp-listen-port 6653 controllers/controller_baseline_fixed.py

# Terminale 2:
sudo python3 topologies/topology_1.py
```

In alcune installazioni, se `ryu-manager` non è sul PATH del superutente, non è un problema: eseguire il controller come utente ordinario; Mininet richiede `sudo`. Se la porta 6653 è occupata o Ryu usa una diversa porta, uniformare controller e topologia. In Mininet verificare `net` e `pingall` (non necessariamente il primo ping riesce durante l'apprendimento MAC).

## 3. Esperimento senza mitigazione

Nel prompt `mininet>` lanciare il server UDP/TCP in background e i client:

```text
h3 iperf -s -u -p 5001 > /tmp/h3_udp.log 2>&1 &
h3 iperf -s -p 5000 > /tmp/h3_tcp.log 2>&1 &
h2 iperf -c 10.0.0.3 -p 5000 -t 60 &
h1 iperf -c 10.0.0.3 -u -b 3M -p 5001 -t 60 &
```

Il test baseline usa **3 Mbps UDP**, come indicato nella sezione 4.2 della relazione. Il lancio in background è una proposta operativa per facilitare la replica. Il bitrate della fase variabile è invece documentato e fornito nel file originale. Lanciare i client con un ordine controllato e conservare i timestamp. Eseguire **solo nella VM Mininet**.

## 4. Mitigazione: scegli una variante

Fermare la CLI con `exit`, pulire con `sudo mn -c` e arrestare il controller precedente. In **Terminale 1**, da root del repository:

| Scenario | Controller | JSON necessario |
|---|---|---|
| Port blocking, versione precedente | `controllers/controller_host_info_json_v3.py` | `config/host_info_with_address.json` |
| Port blocking dinamico, topologia 2 | `controllers/controller_host_info_json_FINALE.py` | `config/host_info_net2.json` |
| IP blocking, topologia 2 | `controllers/controller_host_info_json_IP_v4.py` | `config/host_info_net2.json` |

Gli script originali aprono il JSON tramite **percorso relativo**, quindi creare un link simbolico nella radice prima dell'avvio:

```bash
ln -sf config/host_info_net2.json host_info_net2.json
ryu-manager --ofp-tcp-listen-port 6653 controllers/controller_host_info_json_FINALE.py
```

Nel **Terminale 2**:

```bash
sudo python3 topologies/topology_2.py
```

Per la variante `v3.py` usare `ln -sf config/host_info_with_address.json host_info_with_address.json`. Per la prova link S1–S3 descritta nel PDF, l'originale `FINALE.py` va configurato a leggere `host_info_net2_block.json`, che include valori `null`; **non** provarlo senza correzioni al codice (vedi LIMITATIONS). Non eseguire contemporaneamente varianti di controller sulla stessa porta.

## 5. Traffico variabile

Nella CLI Mininet, dopo avere lanciato il server UDP (`h3 iperf -s -u -p 5001 &`) e TCP, lanciare:

```text
h1 bash scripts/bitrate_var_headless.sh &
```

La CLI Mininet usa comandi di host e path del filesystem della VM: utilizzare un **percorso assoluto** in caso il comando relativo non venga risolto. La sequenza originale è **4 Mbps per 20 s, 1 Mbps per 20 s, 6 Mbps per 20 s**, con 1 s di pausa fra le fasi. Il file `bitrate_var_original.sh` necessita di `xterm` e ambiente grafico, ed era pensato per essere lanciato dentro il namespace host.

## 6. Raccolta evidenze

Eseguire in Mininet prima del traffico (per esempio):

```text
h3 tcpdump -i h3-eth0 -w /tmp/sdn-h3.pcap 'tcp or udp' &
```

Salvare throughput iperf, traffico ricevuto, perdita UDP, ritrasmissioni TCP, log controller e condizioni del test. Filtri Wireshark utili: `udp`, `tcp`, `tcp.analysis.retransmission`, `ip.src == 10.0.0.4`. Conservare i file cattura separatamente; non sono stati forniti gli originali. Stop: `exit` dalla CLI, `sudo mn -c`, arrestare controller e processi iperf/tcpdump residui.

## 7. Criticità e confronto scientifico

- La soglia originale è `2 * 10**6` bit/s con polling ogni 5 s; la stima deriva da differenze dei byte ricevuti sulla porta.
- Sono possibili falsi positivi: la soglia sul volume non distingue intrinsecamente traffico malevolo da traffico legittimo.
- Il codice originale usa `eval()` per interpretare le chiavi JSON: usare **solo file fidati** o sostituirlo con `ast.literal_eval()` previa validazione.
- Il controller usa thread e manipolazione di flow OpenFlow; `OFPP_NORMAL` non equivale sempre a ripristinare la policy precedente e può interagire in modo diverso con OVS. La logica non va considerata pronta per produzione.
- Il JSON `host_info_net2_block.json` contiene `null`; il codice IP utilizza `.get()` su valori letti dal JSON e non è adatto a questa configurazione.
- Sono disponibili gli originali `controller.py` e `topology.py`, ma la topologia originale caricata non coincide con gli scenari descritti nella relazione. Non sono disponibili i sorgenti originali delle topologie a 3/4 host, i PCAP/CSV o tutte le versioni delle dipendenze. Di conseguenza non si garantisce una riproduzione pixel-perfect dei grafici originali.

## 8. Originali e verifiche pre-esecuzione

- `controllers/controller_original.py`: file originale ricevuto, con typo nel parser (`ofproto_parunser`). `controllers/controller_baseline_fixed.py`: copia con **sola** sostituzione del nome dell'attributo.
- `topologies/topology_original.py`: file originale ricevuto, che crea `h1`, `h2` e `s1`, `s2`, `s3`; **non** è la topologia 1 della relazione.
- `topologies/topology_1.py` e `topologies/topology_2.py`: ricostruzioni di laboratorio da PDF/DOCX.
- Le 90 figure in `assets/original-report` sono estratte dal Word; **non** sono riproduzioni ottenute eseguendo il codice qui.

Verificare prima le versioni (`python3 --version`, `ryu-manager --version`, `mn --version`, `ovs-vsctl --version`, `iperf -v`) e salvare le informazioni insieme ai log. Non è stata eseguita una prova end-to-end in VM durante la preparazione della repository.
