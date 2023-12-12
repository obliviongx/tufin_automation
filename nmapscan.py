import nmap
import time
import json
nm = nmap.PortScanner()
#Add subnets to scan to the Subnets Array
subnets=['192.168.252.0/24','192.168.1.0/24']
for subnet in subnets:
    nm.scan(subnet, arguments='-sV --script vulscan/vulscan.nse')
    json_output={}
    nm.scan(subnet)
    for host in nm.all_hosts():
        json_output['nmap_host']=host
        for proto in nm[host].all_protocols():
            if proto not in ["tcp", "udp"]:
                continue
            json_output['nmap_protocol']=proto
            lport = list(nm[host][proto].keys())
            lport.sort()
            for port in lport:
                hostname = ""
                json_output['nmap_port']=port
                for h in nm[host]["hostnames"]:
                    hostname = h["name"]
                    json_output['nmap_hostname']=hostname
                    hostname_type = h["type"]
                    json_output['nmap_hostname_type']=hostname_type
                    json_output['nmap_port_name']=nm[host][proto][port]["name"]
                    json_output['nmap_port_state']=nm[host][proto][port]["state"]
                    json_output['nmap_port_product']=nm[host][proto][port]["product"]
                    json_output['nmap_port_extrainfo']=nm[host][proto][port]["extrainfo"]
                    json_output['nmap_port_reason']=nm[host][proto][port]["reason"]
                    json_output['nmap_port_version']=nm[host][proto][port]["version"]
                    json_output['nmap_port_conf']=nm[host][proto][port]["conf"]
                    json_output['nmap_port_cpe']=nm[host][proto][port]["cpe"]
                    with open("/var/ossec/logs/active-responses.log", "a") as active_response_log:
                        active_response_log.write(json.dumps(json_output))
                        active_response_log.write("\n")
                time.sleep(2)
