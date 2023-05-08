from genie.testbed import load
from pyats_genie_command_parse import GenieCommandParse
from pyats.topology import loader, Device, Interface, Link
from pyats.utils.secret_strings import SecretString
import pprint
import yaml
import sys
import traceback
import re

class Crawl_create:
    def __init__(self,test_bed_file):
        with open(test_bed_file, 'r') as tbfile:
            self.testbed_dict = yaml.safe_load(tbfile)
        self.testbed = loader.load(test_bed_file)
        self.current_device = list(self.testbed_dict["devices"].keys())[0]
        self.visited_switches = []
    

    def _get_cdp_info(self,testbed):
        self.visited_switches.append(self.current_device)
        command = 'show cdp nei detail'
        try:
            dev = testbed.devices[self.current_device]
            dev.connect(learn_hostname=True,goto_enable=False,init_exec_commands=[],init_config_commands=[])
            parse_object = GenieCommandParse(nos=dev.os)
            cdp = dev.default.execute(command)
            dev.disconnect()
            cdp_parsed =  parse_object.parse_string(show_command = command, show_output_data = cdp)
            return cdp_parsed
        except Exception as e:
            sys.stderr.write(f"Could not connect to device {self.current_device} Error is {e}")  
            #traceback.print_exc() 
            return {}

    def _add_cdp_device_to_testbed(self, cdp_object,testbed):
        for index in cdp_object['index']:
            software_version = cdp_object["index"][index]["software_version"] 
            try: 
                ip_address = list(cdp_object['index'][index]["management_addresses"].keys())[0]
                print(f"{cdp_object['index'][index]['device_id']} does not have a IP address!!!------------------------<<<<<<<<<<<<")
                if cdp_object['index'][index]['device_id'] not in list(testbed.devices.keys()):
                    my_os = "ios" if re.search("ios",software_version,re.IGNORECASE) else software_version.split(",")[0]
                    new_device = Device(cdp_object['index'][index]['device_id'],
                                     os = my_os,
                                     connections = {'cli':
                                                    {'protocol':'ssh',
                                                  'ip' : ip_address}},
                                    credentials = testbed.devices[self.current_device].credentials,
                                    )
                    testbed.add_device(new_device)
            except:
                print("No Management address")
        return testbed

    def create_yml_file_from_topology(self,testbed):
        first_device = list(self.testbed_dict["devices"].keys())[0]
        topology_dict = {"devices":{},"testbed":{
            "name": testbed.name,
            "credentials":self.testbed_dict["devices"][first_device]["credentials"]
                        }}
        for device in testbed.devices:
            try:
                my_ip = str(testbed.devices[device].connections.cli.ip)
            except:
                my_ip = testbed.devices[device].connections.cli.ip
            topology_dict["devices"][device] = {
                "connections":{"cli":{
                            "ip": my_ip,
                            "protocol":"ssh"
                }},
                        "os":testbed.devices[device].os,
                    }
            
        with open(f"{testbed.name}.yml", 'w') as tbfile:
            yaml.dump(topology_dict,tbfile)
        return topology_dict
    
    def cdp_crawler(self,testbed):
        dev_compy = testbed.devices.copy()
        cdp = {}
        for device in dev_compy:
            if device not in self.visited_switches:
                self.current_device = device
                cdp = self._get_cdp_info(testbed)
                if cdp:
                    testbed = self._add_cdp_device_to_testbed(cdp,testbed)
                #Go down one level in the search tree
                self.cdp_crawler(testbed)
        return testbed


if __name__ == "__main__":
    cr = Crawl_create('SantiamCORP.yaml')
    tb = cr.cdp_crawler(cr.testbed)
    cr.create_yml_file_from_topology(tb)

