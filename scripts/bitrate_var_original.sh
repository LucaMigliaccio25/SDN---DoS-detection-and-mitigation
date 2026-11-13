#!/bin/bash
 
# Avvia iperf server
#xterm -e "h1 iperf -s &" &
 
# Genera traffico con bitrate variabile
xterm -e "iperf -c 10.0.0.3 -u -b 4M -t 20 -p 5001; sleep 1;
          iperf -c 10.0.0.3 -u -b 1M -t 20 -p 5001; sleep 1;
          iperf -c 10.0.0.3 -u -b 6M -t 20 -p 5001"
