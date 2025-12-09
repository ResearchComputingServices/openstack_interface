import os
import time
import random
import logging

from pprint import pprint

from novaclient import client as novaclient
from neutronclient.v2_0 import client as neutronclient
from glanceclient import client as glanceclient
from keystoneauth1 import loading
from keystoneauth1 import session as keystone_session
from keystoneclient.v3 import client as keystone_client

# Initialize logger for OpenStack Interface
logger = logging.getLogger('cloudman.app.openstack')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

NOVA_API_VERSION = "2.0"
GLANCE_API_VERSION = "2"

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
                 vm_setup_script_path : str = None,
                 external_network_id : str = 'bb005c60-fb45-481a-97fb-f746033e1c5d',
                 key_name : str = 'newmaster'):

        logger.info("Initializing OpenStackInterface")
        # TODO: add error checking for the script paths
        self.vm_setup_script_path = vm_setup_script_path
        self.key_name = key_name

        # Read the VM setup script file as a bytes object
        self.vm_setup_script = None
        if self.vm_setup_script_path is not None:
            logger.debug(f"Loading VM setup script from: {vm_setup_script_path}")
            with open(self.vm_setup_script_path, 'r') as f:
                self.vm_setup_script = f.read()

        # set the external network ID
        self.external_network_id = external_network_id
        logger.debug(f"External network ID: {external_network_id}")

        # initialize the OpenStack session
        logger.info("Initializing OpenStack session")
        self.openstack_session = self.init_openstack_session()

        # initialize the OpenStack clients
        logger.info("Initializing OpenStack clients")
        self.initialize_clients()

        # get the list of projects since you have to be admin to list projects
        logger.debug("Fetching project list")
        self.project_list = self.ks_client.projects.list()
        logger.info(f"OpenStackInterface initialized with {len(self.project_list)} projects")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def set_project_name_env_var(self, project_name: str):

        os.environ[OS_PROJECT_NAME] = project_name

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_project_name_env_var(self):

        return os.environ.get(OS_PROJECT_NAME, None)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_creds(self):

        d = {}

        for env_var, key in zip(NOVA_CREDS_ENV_VARS, NOVA_CREDS_KEYS):
            value = os.environ.get(env_var, None)
            if value is not None:
                d[key] = value
            else:
                raise ValueError(f"Environment variable {env_var} is not set."
                                    f"Please set it before running the script.")

        return d

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def init_openstack_session(self):
        """
        Initialize the OpenStack session with the credentials.
        """
        creds = self.get_creds()
        loader = loading.get_plugin_loader('password')
        auth = loader.load_from_options(**creds)

        return keystone_session.Session(auth=auth,verify=os.environ['OS_CACERT'])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def initialize_clients(self):
        """
        Initialize the OpenStack clients.
        """
        if self.openstack_session:
            self.nova_client = novaclient.Client(NOVA_API_VERSION, session=self.openstack_session)
            self.glance_client = glanceclient.Client(GLANCE_API_VERSION, session=self.openstack_session)
            self.neutron_client = neutronclient.Client(session=self.openstack_session)
            self.ks_client = keystone_client.Client(session=self.openstack_session)
        else:
            raise ValueError("OpenStack session is required to initialize Neutron client.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def check_project_exists(self, project_name=None):
        """
        Check if a project exists.
        """
        if project_name is None:
            raise ValueError("Project name must be provided to check existence.")

        for project in self.project_list:
            if project.name == project_name:
                return True

        return False

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def project_name_from_id(self, project_id=None):
        """
        Get the project name from its ID.
        """
        project = self.ks_client.projects.get(project_id)
        if project is None:
            raise ValueError(f"Project with ID {project_id} does not exist.")

        return project.name

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def change_project( self,
                        project_name=None,
                        project_id=None):
        """
        Change the current project by setting the OS_PROJECT_NAME environment variable.
        """
        # check that at least one of project_name or project_id is provided
        if project_name is None and project_id is None:
            raise ValueError("Either project name or project ID must be provided to change the project.")

        # if project_id is provided, get the project name
        if project_id is not None:
            try:
                project_name = self.project_name_from_id(project_id=project_id)
            except ValueError as e:
                raise e

        # check that the project exists
        if not self.check_project_exists(project_name=project_name):
            error_msg = f"Project with name {project_name} does not exist."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # after all checks, set the project name in the environment variable
        logger.info(f"Switching to project: {project_name}")
        self.set_project_name_env_var(project_name)
        self.openstack_session = self.init_openstack_session()
        self.initialize_clients()
        logger.debug(f"Successfully switched to project: {project_name}")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _allocate_fip(self):

        """
        Allocate a floating IP to the ACTIVE PROJECT.
        """

        body = {"floatingip": {"floating_network_id": self.external_network_id}}

        try:
            logger.debug("Allocating new floating IP")
            fip = self.neutron_client.create_floatingip(body)['floatingip']
            logger.info(f"Allocated floating IP: {fip.get('floating_ip_address')}")
            return fip
        except Exception as e:
            logger.error(f"Error allocating floating IP: {str(e)}")
            return None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get_fip(self):
        """
        Get a floating IP from the ACTIVE PROJECT.
        """

        # First check if there are any floating IPs allocated to the project
        # if not then try to allocate one
        if self.get_num_allocated_floating_ips() == 0:
            logger.info("No floating IPs allocated to the project. Allocating one")
            self._allocate_fip()

        floating_ips = self.neutron_client.list_floatingips()['floatingips']

        for fip in floating_ips:
            if not fip['port_id']:
                logger.debug(f"Found available floating IP: {fip['floating_ip_address']}")
                return fip

        error_msg = "No available floating IPs found."
        logger.error(error_msg)
        raise ValueError(error_msg)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get_fip_associated_to_port(self, port_id):
        # try to find the floating IP associated with the port
        floating_ips = self.neutron_client.list_floatingips()['floatingips']
        fip = None
        for floating_ip in floating_ips:
            if floating_ip['port_id'] == port_id:
                fip = floating_ip
                break

        if fip is None:
            raise ValueError(f"No floating IP associated with port ID: {port_id}")

        return fip

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _disassociate_fip(self, fip):

        try:
            logger.info(f"Disassociating floating IP: {fip['floating_ip_address']}")
            self.neutron_client.update_floatingip(fip['id'], {"floatingip": {"port_id": None}})
            logger.debug(f"Disassociated Floating IP {fip['floating_ip_address']}")
        except Exception as e:
            logger.error(f"Error disassociating floating IP: {str(e)}")
            raise e

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _associate_fip(self, fip, port_id):

        try:
            logger.info(f"Associating floating IP {fip['floating_ip_address']} with port {port_id}")
            self.neutron_client.update_floatingip(fip['id'], {"floatingip": {"port_id": port_id}})
            logger.debug(f"Associated Floating IP {fip['floating_ip_address']} with port ID {port_id}")
        except Exception as e:
            logger.error(f"Error associating floating IP: {str(e)}")
            raise e

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _release_fip(self, fip=None):
        """
        Release a floating IP by its ID.
        """
        if fip:
            logger.info(f"Releasing floating IP: {fip.get('floating_ip_address')}")
            self.neutron_client.delete_floatingip(fip.get('id'))
            logger.debug(f"Floating IP {fip.get('floating_ip_address')} released")
        else:
            raise ValueError("Floating IP data structure must be provided to release the floating IP.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def detach_fip_from_vm(self, vm):

        """
        Disassociate a floating IP from a port.
        """

        logger.info(f"Detaching floating IP from VM: {vm.name}")
        # set the active project to the VM's tenant
        self.change_project(project_id=vm.tenant_id)

        # try to get the port ID of the VM
        try:
            port_id = self.get_vm_port_id(vm)
            logger.debug(f"Found port ID for VM {vm.name}: {port_id}")
        except ValueError as e:
            raise e

        # try to get the floating IP associated with the port
        try:
            fip = self._get_fip_associated_to_port(port_id)
            logger.debug(f"Found Floating IP {fip['floating_ip_address']} associated with port ID {port_id}")
        except ValueError as e:
            raise e

        # try to disassociate the floating IP
        try:
            self._disassociate_fip(fip)
        except Exception as e:
            raise e

        # release the floating IP so it can be used in another project
        try:
            self._release_fip(fip)
            logger.info(f"Successfully detached floating IP from VM: {vm.name}")
        except Exception as e:
            raise e

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def attach_fip_to_vm(self, vm):
        """
        Associate a floating IP to a port.
        """

        logger.info(f"Attaching floating IP to VM: {vm.name}")
        # set the active project to the VM's tenant
        self.change_project(project_id=vm.tenant_id)

        # try to get a floating IP
        try:
            fip = self._get_fip()
            logger.debug(f"Found available Floating IP: {fip['floating_ip_address']}")
        except ValueError as e:
            raise e

        # try to get the port ID of the VM
        try:
            port_id = self.get_vm_port_id(vm)
            logger.debug(f"Found port ID for VM {vm.name}: {port_id}")
        except ValueError as e:
            raise e

        try:
            self._associate_fip(fip, port_id)
            logger.info(f"Successfully attached floating IP {fip['floating_ip_address']} to VM: {vm.name}")
        except Exception as e:
            raise e

        return fip['floating_ip_address']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def create_flavor(self, vcpus, ram, disk):

        flavour_name = f"{vcpus}cpu{ram}gb.{disk}g"

        return  self.nova_client.flavors.create(name=flavour_name,
                                                ram=ram * 1024,  # MB
                                                vcpus=vcpus,
                                                disk=disk)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def check_floating_ips_available(self):
        """
        Check if there are any floating IPs available in the ACTIVE PROJECT.
        """

        logger.debug("Checking floating IP availability")
        fip = self._allocate_fip()

        if fip:
            # release the allocated floating IP since this is just a check
            logger.debug("Floating IPs are available")
            return True
        else:
            logger.warning("No floating IPs available")
            return False

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_num_allocated_floating_ips(self):
        """
        Get the number of allocated floating IPs.
        """
        floating_ips = self.neutron_client.list_floatingips()['floatingips']
        num_allocated = len(floating_ips)

        return num_allocated

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_vm(self, vm_name=None):
        """
        Get a VM by its name.
        """
        if vm_name is None:
            raise ValueError("VM name must be provided to get the VM.")

        logger.debug(f"Looking up VM by name: {vm_name}")
        for server in self.nova_client.servers.list(search_opts={'all_tenants': True}):
            if server.name == vm_name:
                logger.debug(f"VM found: {vm_name}")
                return server

        error_msg = f"VM with name {vm_name} not found."
        logger.warning(error_msg)
        raise ValueError(error_msg)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_vm_port_id(self, vm):
        """
        Get the port ID of a VM.
        """
        server_interfaces = self.nova_client.servers.interface_list(vm.id)
        if not server_interfaces:
            raise ValueError(f"No interfaces found for VM with ID {vm.id}.")

        port_id = server_interfaces[0].port_id

        return port_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_projects(self):
        """
        Get the list of projects.
        """
        return self.project_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_os_image_list(self):
        """
        Get the list of images from the Glance client.
        """
        logger.debug("Fetching OS image list from Glance")
        glance_images = self.glance_client.images.list()
        image_list = []

        for image in glance_images:
            image_list.append(image['name'])

        logger.debug(f"Retrieved {len(image_list)} images from Glance")
        return image_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # TODO: change this function name to reflect its purpose better (ie get_faculty_network_id)

    def get_default_network_id(self):
        for network in self.neutron_client.list_networks()['networks']:
            if network['name'].lower() == 'rcs':
                return network['id']

    def get_network_id(self,
                       faculty_name : str):
        """
        Get the network ID for a given faculty name.
        """
        network_id = self.get_default_network_id()  # default to rcs network

        for network in self.neutron_client.list_networks()['networks']:
            if network['name'].lower() == faculty_name.lower():
                network_id = network['id']
                break

        return network_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_vm_by_floating_ip(self,
                              floating_ip_address : str):

        logger.debug(f"Looking up VM by floating IP: {floating_ip_address}")
        servers = self.nova_client.servers.list(search_opts={'all_tenants': True})

        for server in servers:
            addresses = server.addresses
            for network in addresses.values():
                for addr in network:
                    if addr.get('OS-EXT-IPS:type') == 'floating' and addr.get('addr') == floating_ip_address:
                        logger.debug(f"VM found with floating IP {floating_ip_address}: {server.name}")
                        return server

        logger.warning(f"No VM found with floating IP: {floating_ip_address}")
        return None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_flavor_list(self):
        """
        Get the list of flavors from the Nova client.
        """
        return self.nova_client.flavors.list()

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
        glance_images = self.glance_client.images.list()
        image = next((img for img in glance_images if img.name == selected_image_name), None)

        return image

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_vm_hypervisor_name(self,
                               vm_id : str):

        full_server_name = self.nova_client.servers.get(vm_id).to_dict().get("OS-EXT-SRV-ATTR:host")

        # this removes the domain part of the hypervisor name (.maas)
        hypervisor_name = full_server_name.split('.')[0] if full_server_name else None

        return hypervisor_name

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def create_vm(self,
                  project_name : str,
                  hostname : str,
                  flavour,
                  image,
                  networks : list):

        logger.info(f"Creating VM: hostname={hostname}, project={project_name}, flavor={flavour.name}")
        self.change_project(project_name=project_name)

        # create the VM using the Nova client
        try:
            logger.debug(f"Requesting VM creation from Nova: hostname={hostname}, image={image.name if hasattr(image, 'name') else image}")
            vm = self.nova_client.servers.create(   name=hostname,
                                                    image=image,
                                                    flavor=flavour,
                                                    key_name=self.key_name,
                                                    nics=networks,
                                                    userdata=self.vm_setup_script)


            # wait for the VM to become ACTIVE
            while vm.status != 'ACTIVE':
                logger.debug(f"Waiting for VM {hostname} to become ACTIVE. Current status: {vm.status}")
                time.sleep(1)
                vm = self.nova_client.servers.get(vm.id)
                if vm.status == 'ERROR':
                    fault_info = getattr(vm, 'fault', None)
                    if fault_info:
                        fault_code = fault_info.get('code', 'Unknown')
                        fault_message = fault_info.get('message', 'No message available')
                        fault_details = fault_info.get('details', '')
                        error_msg = f"Failed to create VM: VM entered ERROR state. Fault code: {fault_code}, Message: {fault_message}"
                        if fault_details:
                            logger.error(f"{error_msg}\nDetails: {fault_details}")
                        else:
                            logger.error(error_msg)
                    else:
                        error_msg = f"Failed to create VM: VM entered ERROR state (no fault details available)."
                        logger.error(error_msg)
                    raise ValueError(error_msg)

            logger.info(f"VM {hostname} is now ACTIVE")
            return vm

        except novaclient.exceptions.Forbidden as e:
            raise ValueError(f"Failed to create VM: Permission denied to create VM in project '{self._get_creds()}': {e}")

        except Exception as e:
            raise ValueError(f"Failed to create VM:{type(e).__name__}:{e}")


# =================================================================================================