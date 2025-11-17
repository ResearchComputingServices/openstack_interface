import datetime
import os
import time

from novaclient import client as novaclient
from neutronclient.v2_0 import client as neutronclient
from glanceclient import client as glanceclient
from keystoneauth1 import loading
from keystoneauth1 import session as keystone_session
from keystoneclient.v3 import client as keystone_client

from pprint import pprint


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# OpenStack Nova and Glance API Version and Credentials
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# TODO: clean up the definitions below - some are not used - maybe use a dataclass?
NOVA_API_VERSION = "2.0"

OS_USERNAME = 'OS_USERNAME'
OS_PASSWORD = 'OS_PASSWORD'
OS_AUTH_URL = 'OS_AUTH_URL'
OS_PROJECT_NAME = 'OS_PROJECT_NAME'
OS_PROJECT_DOMAIN_NAME = 'OS_PROJECT_DOMAIN_NAME'
OS_USER_DOMAIN_NAME = 'OS_USER_DOMAIN_NAME'
OS_CACERT = 'OS_CACERT'

NOVA_CREDS_ENV_VARS = [ OS_USERNAME,
                        OS_PASSWORD,
                        OS_AUTH_URL,
                        OS_PROJECT_NAME,
                        OS_PROJECT_DOMAIN_NAME,
                        OS_USER_DOMAIN_NAME,
                        OS_CACERT]

NOVA_CREDS_KEYS = [
    'username',
    'password',
    'auth_url',
    'project_name',
    'project_domain_name',
    'user_domain_name',
]

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class OpenStackInterface:

    def __init__(self,
                 vm_setup_script_path : str,
                 gpu_setup_script_path : str,
                 add_user_script_path : str,
                 final_setup_script_path : str,
                 private_key_path : str,
                 external_network_id : str = 'bb005c60-fb45-481a-97fb-f746033e1c5d'):

        # TODO: add error checking for the script paths
        # paths to the setup scripts to be copied to the VMs
        self.vm_setup_script_path = vm_setup_script_path
        self.gpu_setup_script_path = gpu_setup_script_path
        self.add_user_script_path = add_user_script_path
        self.final_setup_script_path = final_setup_script_path
        self.private_key_path = private_key_path

        # initialize the OpenStack clients
        self.nova = None
        self._init_nova_client()

        self.glance = None
        self._init_glance_client()

        self.neutron = None
        self._init_neutron_client()

        self.keystone = None
        self._init_keystone_client()

        # Read the VM setup script file as a bytes object
        self.vm_setup_script = None
        with open(self.vm_setup_script_path, 'r') as f:
            self.vm_setup_script = f.read()

        # used for associating floating IPs
        self.external_network_id = external_network_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get_creds(self):

        d = {}

        for env_var, key in zip(NOVA_CREDS_ENV_VARS, NOVA_CREDS_KEYS):
            value = os.environ.get(env_var, None)
            if value is not None:
                d[key] = value
            else:
                raise ValueError(f"Environment variable {env_var} is not set. Please set it before running the script.")

        return d

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _set_project_name(self, project_name: str):

        os.environ[OS_PROJECT_NAME] = project_name

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _init_neutron_client(self):
        """
        Initialize the Neutron client with the credentials.
        """
        creds = self._get_creds()

        loader = loading.get_plugin_loader('password')
        auth = loader.load_from_options(**creds)

        sess = keystone_session.Session(auth=auth,verify=os.environ['OS_CACERT'])

        self.neutron = neutronclient.Client(session=sess)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _init_nova_client(self):
        """
        Initialize the Nova client with the credentials.
        """

        creds = self._get_creds()

        loader = loading.get_plugin_loader('password')
        auth = loader.load_from_options(**creds)

        # TODO: I think we should be able to get rid of this?
        sess = keystone_session.Session(auth=auth,verify=os.environ['OS_CACERT'])

        self.nova = novaclient.Client(NOVA_API_VERSION, **creds, cacert=os.environ['OS_CACERT'])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _init_glance_client(self):
        """
        Initialize the Glance client with the credentials.
        """
        creds = self._get_creds()

        loader = loading.get_plugin_loader('password')
        auth = loader.load_from_options(**creds)

        sess = keystone_session.Session(auth=auth,verify=os.environ['OS_CACERT'])

        self.glance = glanceclient.Client("2", session=sess)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _init_keystone_client(self):
        """
        Initialize the Keystone client with the credentials.
        """
        creds = self._get_creds()

        loader = loading.get_plugin_loader('password')
        auth = loader.load_from_options(**creds)

        sess = keystone_session.Session(auth=auth,verify=os.environ['OS_CACERT'])

        self.keystone = keystone_client.Client(session=sess)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _switch_project(self, project_name: str):
        """
        Switch the Nova client to a different project.
        """
        self._set_project_name(project_name)

        creds = self._get_creds()
        loader = loading.get_plugin_loader('password')
        auth = loader.load_from_options(**creds)

        # TODO: I think we should be able to get rid of this?
        sess = keystone_session.Session(auth=auth,verify=os.environ['OS_CACERT'])

        self.nova = novaclient.Client(NOVA_API_VERSION, **creds, cacert=os.environ['OS_CACERT'])
        self.neutron = neutronclient.Client(session=sess)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_projects(self):
        """
        Get the list of projects from the Keystone client.
        """
        return self.keystone.projects.list()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_os_image_list(self):
        """
        Get the list of images from the Glance client.
        """
        glance_images = self.glance.images.list()
        image_list = []

        for image in glance_images:
            image_list.append(image['name'])

        return image_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_os_vm_list(self):
        """
        Get the list of virtual machines from the Nova client.
        """
        return self.nova.servers.list()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_network_id(self,
                       faculty_name : str):
        """
        Get the network ID for a given faculty name.
        """

        network_id = '41117794-0b4c-4dd3-8f2b-7d9bb458e968'  # default to rcs network

        for network in self.neutron.list_networks()['networks']:
            if network['name'].lower() == faculty_name.lower():
                network_id = network['id']
                break

        return network_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_networks_ids(self):
        """
        Get the list of networks from the Neutron client.
        """
        networks = self.neutron.list_networks()['networks']

        network_list = [network['id'] for network in networks]

        return network_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_networks(self):
        """
        Get the list of networks from the Neutron client.
        """
        return self.neutron.list_networks()['networks']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_security_groups(self):
        """
        Get the list of security groups from the Nova client.
        """
        security_groups = self.nova.security_groups.list()
        security_group_list = []

        for sg in security_groups:
            security_group_list.append(sg['name'])

        return security_group_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_flavor_list(self):
        """
        Get the list of flavors from the Nova client.
        """
        return self.nova.flavors.list()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def create_flavor(self, vcpus, ram, disk):

        flavour_name = f"{vcpus}cpu{ram}gb.{disk}g"

        return  self.nova.flavors.create(   name=flavour_name,
                                            ram=ram * 1024,  # MB
                                            vcpus=vcpus,
                                            disk=disk)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def assosciate_floating_ip(self, vm, network_id):

        try:
            floating_ip = self.neutron.create_floatingip({'floatingip': {'floating_network_id': network_id}})
        except Exception as e:
            raise ValueError(f"Failed to allocate floating IP: {e}")

        if floating_ip:
            floating_ip_id = floating_ip['floatingip']["id"]
            floating_ip_address = floating_ip['floatingip']["floating_ip_address"]

        # Wait for the VM to be in ACTIVE state
        time.sleep(10)

        ports = self.neutron.list_ports(device_id=vm.id)

        for port in ports['ports']:
            port_id= port['id']

            # Assign the floating IP to the port
            try:
                self.neutron.update_floatingip(floating_ip_id, {'floatingip': {'port_id': port_id}})
            except Exception as e:
                print(f"Error assigning floating IP {floating_ip_address} to port {port_id}: {e}")

        return floating_ip_address

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def release_floating_ip(self,
                            floating_ip_address : str):
        try:
        #    self.neutron.delete_floatingip(floating_ip_address)
            for fip in self.neutron.list_floatingips()['floatingips']:
                if fip['floating_ip_address'] == floating_ip_address:
                    self.neutron.update_floatingip(fip['id'], {'floatingip': {'port_id': None}})
                    self.neutron.delete_floatingip(fip['id'])
                    return True

        except Exception as e:
            raise e

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _check_floating_ips_available(self):

        for fip in self.neutron.list_floatingips()['floatingips']:
            if fip.get('port_id') is None:
                self.release_floating_ip(fip['floating_ip_address'])
                return True

        return False

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def create_vm(self,
                  project_name : str,
                  hostname : str,
                  flavour,
                  image,
                  networks : list):

        self._switch_project(project_name)

        # check to see if there are any floating IPs available in the project
        if not self._check_floating_ips_available():
            raise ValueError(   f"No floating IPs available in project '{project_name}'. "
                                f"Cannot create VM.")

        # create the VM using the Nova client
        try:
            vm = self.nova.servers.create(  name=hostname,
                                            image=image,
                                            flavor=flavour,
                                            key_name='newmaster',
                                            nics=networks,
                                            userdata=self.vm_setup_script)

            if vm.status == 'ERROR':
                raise ValueError(f"Failed to create VM: VM entered ERROR state.")

        except novaclient.exceptions.Forbidden as e:
            raise ValueError(f"Failed to create VM: Permission denied to create VM in project '{self._get_creds()}': {e}")

        except Exception as e:
            raise ValueError(f"Failed to create VM:{type(e).__name__}:{e}")

        # Associate a floating IP to the VM
        try:
            floating_ip = self.assosciate_floating_ip(vm, self.external_network_id)
        except Exception as e:
            raise ValueError(f"Failed to associate floating IP to VM '{hostname}': {e}")

        return vm, floating_ip

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_vm_by_floating_ip(self,
                              floating_ip_address : str):

        servers = self.nova.servers.list(search_opts={'all_tenants': True})

        for server in servers:
            addresses = server.addresses
            for network in addresses.values():
                for addr in network:
                    if addr.get('OS-EXT-IPS:type') == 'floating' and addr.get('addr') == floating_ip_address:
                        return server

        return None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get_server_by_name(self,
                            vm_hostname : str):

        servers = self.nova.servers.list(search_opts={'all_tenants': True})

        vms = [s for s in servers if s.name == vm_hostname]

        if len(vms) == 0:
            raise ValueError(f"VM {vm_hostname} not found")
        elif len(vms) > 1:
            raise ValueError(f"Multiple VMs with the name {vm_hostname} found")
        else:
            return vms[0]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def delete_vm(self,
                  vm_hostname : str):
        try:
            vm = self._get_server_by_name(vm_hostname)
            self.nova.servers.delete(vm.id)
            return True
        except Exception as e:
            raise ValueError(f"Failed to delete VM {vm_hostname}: {e}")


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_os_image_by_name(   self,
                                selected_image_name : str):
        """
        Get the image object from the Glance client by name.

        Args:
            image_name (str): The name of the image to retrieve.

        Returns:
            Image object if found, None otherwise.
        """
        glance_images = self.glance.images.list()
        image = next((img for img in glance_images if img.name == selected_image_name), None)

        return image

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_server(self,
                   vm_id : str):

        return self.nova.servers.get(vm_id)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_vm_hypervisor_name(self,
                               vm_id : str):

        return self.get_server(vm_id).to_dict().get("OS-EXT-SRV-ATTR:host")
