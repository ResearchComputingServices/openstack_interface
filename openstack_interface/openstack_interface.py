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

    def __init__(self):
        self.nova = None
        self._init_nova_client()

        self.glance = None
        self._init_glance_client()

        self.neutron = None
        self._init_neutron_client()

        self.keystone = None
        self._init_keystone_client()

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
        creds = self._get_creds()
        creds['project_name'] = project_name

        loader = loading.get_plugin_loader('password')
        auth = loader.load_from_options(**creds)

        # TODO: I think we should be able to get rid of this?
        sess = keystone_session.Session(auth=auth,verify=os.environ['OS_CACERT'])

        self.nova = novaclient.Client(NOVA_API_VERSION, **creds, cacert=os.environ['OS_CACERT'])

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

    def create_vm(self,
                  project_name : str,
                  hostname : str,
                  flavour,
                  image,
                  networks : list):

        self._switch_project(project_name)

        #  Prepare user data for the VM (this is the initial setup script)
        # TODO: remove this hard coding
        script_file_path = '/home/sysadmin/setup-script.sh'

        # Read the script file and use it as user_data
        with open(script_file_path, 'r') as f:
            user_data = f.read()

        # create the VM using the Nova client
        try:
            vm = self.nova.servers.create(  name=hostname,
                                            image=image,
                                            flavor=flavour,
                                            key_name='newmaster',
                                            nics=networks,
                                            userdata=user_data)
        except Exception as e:
            raise ValueError(f"Failed to create VM: {e}")

        # Associate a floating IP to the VM
        # self.assosciate_floating_ip(vm, networks[0]['net-id'])
        floating_ip =self.assosciate_floating_ip(vm, 'bb005c60-fb45-481a-97fb-f746033e1c5d')

        return vm, floating_ip

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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~