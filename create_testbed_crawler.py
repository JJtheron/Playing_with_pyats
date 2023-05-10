from genie.testbed import load
from pyats_genie_command_parse import GenieCommandParse
from pyats.topology import Testbed, loader, Device, Interface, Link
from pyats.utils.secret_strings import SecretString
import pprint
import yaml
import sys
import traceback
import re
import fire
import getpass

class Crawl_create:
    def __init__(self,test_bed_name = "default", os="ios", user = "", password = "", device_name = "first_device", ip_address = "", protocol = "ssh", port = "22"):
        if not user:
            user = input("Username: ")
        if not password:
            password = getpass.getpass(prompt="password: ")
        self.user = user
        self.password = password
        self.testbed = Testbed(test_bed_name,
                               credentials = {"default":{
                                                "username":user,
                                                "password":password
                               } })

        self.testbed.add_device(Device(device_name,os=os,connections={"cli":{
                                "protocol":protocol,
                                "ip":ip_address,
                                "port":port
        }}))
        self.visited_switches = []
        self.cdp_crawler(self.testbed)    
#functions for crawling through environment using cdp
#-----------------------------------------------------------------------------------------------------------------
#VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
    def _get_cdp_info(self,testbed,device):
        command = 'show cdp nei detail'
        try:
            dev = testbed.devices[device]
            dev.connect(learn_hostname=True,goto_enable=False,init_exec_commands=[],init_config_commands=[])
            cdp = dev.default.execute(command)
            dev.disconnect()
        except Exception as e:
            sys.stderr.write(f"Could not connect to device {device} Error is {e}")  
            self.visited_switches.append(device)
            traceback.print_exc() 
            return {},testbed
            
        parse_object = GenieCommandParse(nos=dev.os)
        testbed.devices[dev.hostname] = testbed.devices.pop(device)
        cdp_parsed =  parse_object.parse_string(show_command = command, show_output_data = cdp)
        self.visited_switches.append(dev.hostname)

        return cdp_parsed, testbed

    def _add_cdp_device_to_testbed(self, cdp_object,testbed, device):
        ip_address = ""
        for index in cdp_object['index']:
            if cdp_object['index'][index]['device_id'].split(".")[0].upper() not in [i.split(".")[0].upper() for i in list(testbed.devices.keys())]:
                software_version = cdp_object["index"][index]["software_version"] 
                try: 
                    ip_address = list(cdp_object['index'][index]["management_addresses"].keys())[0]
                except:
                    ip_address = ""
                    print(f"{cdp_object['index'][index]['device_id']} does not have a IP address!!!------------------------<<<<<<<<<<<<")
                my_os = "ios" if re.search("ios",software_version,re.IGNORECASE) else software_version.split(",")[0]
                new_device = Device(cdp_object['index'][index]['device_id'],
                                         os = my_os,
                                         connections = {'cli':
                                                        {'protocol':'ssh',
                                                      'ip' : ip_address}},
                                        credentials = testbed.devices[device].credentials,
                                        )
                if ip_address:
                    testbed.add_device(new_device)
        return testbed
#TODO: LLDP crawler    

#CDP crawler:
    def cdp_crawler(self,testbed):
        dev_copy = testbed.devices.copy()
        cdp = {}
        for device in dev_copy:
            if device.split(".")[0] not in self.visited_switches:
                cdp, testbed = self._get_cdp_info(testbed,device)
                if cdp:
                    testbed = self._add_cdp_device_to_testbed(cdp,testbed, device)
                #Go down one level in the search tree
                self.cdp_crawler(testbed)
        self.testbed = testbed
        return testbed

#functions for crawling through environment using cdp
#-----------------------------------------------------------------------------------------------------------------
#^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    def create_ats_testbed_file(self):
        first_device = list(self.testbed.devices.keys())[0]
        topology_dict = {"devices":{},"testbed":{
            "name": self.testbed.name,
            "credentials":{"default":{
                                      "username":self.user,
                                      "password":SecretString.from_plaintext(self.password).data
                        }}}}
        for device in self.testbed.devices:
            try:
                my_ip = str(self.testbed.devices[device].connections.cli.ip)
            except:
                my_ip = self.testbed.devices[device].connections.cli.ip
            topology_dict["devices"][device] = {
                "connections":{"cli":{
                            "ip": my_ip,
                            "protocol":"ssh"
                }},
                        "os":self.testbed.devices[device].os,
                    }
            
        with open(f"{self.testbed.name}.yml", 'w') as tbfile:
            yaml.dump(topology_dict,tbfile)
        return topology_dict

    def create_hosts_file_ansible(self):
        ansible_hosts = {"all":{"hosts":{}}}
        for device in self.testbed.devices:
            try:
                my_ip = str(self.testbed.devices[device].connections.cli.ip)
            except:
                my_ip = self.testbed.devices[device].connections.cli.ip
            ansible_hosts["all"]["hosts"][device] = {"ansible_host": my_ip }
        
    
        with open(f"ansible_{self.testbed.name}.yml", 'w') as tbfile:
            yaml.dump(ansible_hosts,tbfile)
        return ansible_hosts


if __name__ == "__main__":
    fire.Fire(Crawl_create)
