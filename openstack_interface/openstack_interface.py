import os
import time
import openstack
from openstack.config import loader
from pprint import pprint

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# OpenStack SDK Configuration
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class OpenStackInterface:

    def __init__(self,
                 vm_setup_script_path : str,
                 gpu_setup_script_path : str,
                 monitor_setup_script_path : str):

        # TODO: add error checking for the script paths
        # paths to the setup scripts to be copied to the VMs
        self.vm_setup_script_path = vm_setup_script_path
        self.gpu_setup_script_path = gpu_setup_script_path
        self.monitor_setup_script_path = monitor_setup_script_path

        # Initialize the OpenStack SDK connection
        self.conn = self._init_connection()
        self.current_project = None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _init_connection(self):
        """
        Initialize the OpenStack SDK connection using environment variables.
        """
        # Verify required environment variables are set
        required_vars = [
            'OS_USERNAME', 'OS_PASSWORD', 'OS_AUTH_URL', 'OS_PROJECT_NAME',
            'OS_PROJECT_DOMAIN_NAME', 'OS_USER_DOMAIN_NAME'
        ]

        for var in required_vars:
            if not os.environ.get(var):
                raise ValueError(f"Environment variable {var} is not set. Please set it before running the script.")

        # Create connection using environment variables
        conn = openstack.connect(
            auth_url=os.environ['OS_AUTH_URL'],
            project_name=os.environ['OS_PROJECT_NAME'],
            username=os.environ['OS_USERNAME'],
            password=os.environ['OS_PASSWORD'],
            project_domain_name=os.environ['OS_PROJECT_DOMAIN_NAME'],
            user_domain_name=os.environ['OS_USER_DOMAIN_NAME'],
            verify=os.environ.get('OS_CACERT', True)
        )

        return conn

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _switch_project(self, project_name: str):
        """
        Switch to a different project by creating a new connection.
        """
        self.conn = openstack.connect(
            auth_url=os.environ['OS_AUTH_URL'],
            project_name=project_name,
            username=os.environ['OS_USERNAME'],
            password=os.environ['OS_PASSWORD'],
            project_domain_name=os.environ['OS_PROJECT_DOMAIN_NAME'],
            user_domain_name=os.environ['OS_USER_DOMAIN_NAME'],
            verify=os.environ.get('OS_CACERT', True)
        )
        self.current_project = project_name

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_projects(self):
        """
        Get the list of projects from OpenStack.
        """
        return list(self.conn.identity.projects())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_os_image_list(self):
        """
        Get the list of images from OpenStack.
        """
        images = list(self.conn.image.images())
        image_list = []

        for image in images:
            image_list.append(image.name)

        return image_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_os_vm_list(self):
        """
        Get the list of virtual machines from OpenStack.
        """
        return list(self.conn.compute.servers())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_network_id(self,
                       faculty_name : str):
        """
        Get the network ID for a given faculty name.
        """

        network_id = '41117794-0b4c-4dd3-8f2b-7d9bb458e968'  # default to rcs network

        for network in self.conn.network.networks():
            if network.name.lower() == faculty_name.lower():
                network_id = network.id
                break

        return network_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_networks_ids(self):
        """
        Get the list of network IDs from OpenStack.
        """
        networks = list(self.conn.network.networks())
        network_list = [network.id for network in networks]

        return network_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_networks(self):
        """
        Get the list of networks from OpenStack.
        """
        return list(self.conn.network.networks())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_security_groups(self):
        """
        Get the list of security groups from OpenStack.
        """
        security_groups = list(self.conn.network.security_groups())
        security_group_list = []

        for sg in security_groups:
            security_group_list.append(sg.name)

        return security_group_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_flavor_list(self):
        """
        Get the list of flavors from OpenStack.
        """
        return list(self.conn.compute.flavors())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def create_flavor(self, vcpus, ram, disk):

        flavour_name = f"{vcpus}cpu{ram}gb.{disk}g"

        return self.conn.compute.create_flavor(
            name=flavour_name,
            ram=ram * 1024,  # MB
            vcpus=vcpus,
            disk=disk
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def assosciate_floating_ip(self, vm, network_id):

        try:
            floating_ip = self.conn.network.create_ip(floating_network_id=network_id)
        except Exception as e:
            raise ValueError(f"Failed to allocate floating IP: {e}")

        if floating_ip:
            floating_ip_id = floating_ip.id
            floating_ip_address = floating_ip.floating_ip_address

        # Wait for the VM to be in ACTIVE state
        time.sleep(10)

        ports = list(self.conn.network.ports(device_id=vm.id))

        for port in ports:
            port_id = port.id

            # Assign the floating IP to the port
            try:
                self.conn.network.update_ip(floating_ip_id, port_id=port_id)
            except Exception as e:
                print(f"Error assigning floating IP {floating_ip_address} to port {port_id}: {e}")

        return floating_ip_address

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def release_floating_ip(self,
                            vm_hostname : str,
                            floating_ip_address : str):

        try:
            for fip in self.conn.network.ips():
                if fip.floating_ip_address == floating_ip_address:
                    self.conn.network.update_ip(fip.id, port_id=None)
                    self.conn.network.delete_ip(fip.id)
                    return True

        except Exception as e:
            raise e

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def create_vm(self,
                  project_name : str,
                  hostname : str,
                  flavour,
                  image,
                  networks : list):

        self._switch_project(project_name)

        print(f"Creating VM in project: {project_name}")

        # TODO: check to see if there are any floating IPs available in the project

        # TODO: this needs to be loaded only once
        # Read the script file and use it as user_data
        with open(self.vm_setup_script_path, 'r') as f:
            user_data = f.read()

        # create the VM using the OpenStack SDK
        try:
            vm = self.conn.compute.create_server(
                name=hostname,
                image_id=image.id if hasattr(image, 'id') else image,
                flavor_id=flavour.id if hasattr(flavour, 'id') else flavour,
                key_name='newmaster',
                networks=networks,
                user_data=user_data
            )

        except Exception as e:
            raise ValueError(f"Failed to create VM:{type(e).__name__}:{e}")


        # TODO: instead of hard coding the network ID, we should get it from the Neutron client
        # Associate a floating IP to the VM
        floating_ip = self.assosciate_floating_ip(vm, 'bb005c60-fb45-481a-97fb-f746033e1c5d')

        # TODO: run the 'final.sh' script on the VM to complete the setup

        # TODO: Check if the VM has a GPU and if so run the GPU setup script on the VM

        return vm, floating_ip

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get_server_by_name(self,
                            vm_hostname : str):

        servers = list(self.conn.compute.servers())

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
            self.conn.compute.delete_server(vm.id)
            return True
        except Exception as e:
            raise ValueError(f"Failed to delete VM {vm_hostname}: {e}")


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_os_image_by_name(   self,
                                selected_image_name : str):
        """
        Get the image object from OpenStack by name.

        Args:
            image_name (str): The name of the image to retrieve.

        Returns:
            Image object if found, None otherwise.
        """
        images = list(self.conn.image.images())
        image = next((img for img in images if img.name == selected_image_name), None)

        return image

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_server(self,
                   vm_id : str):

        return self.conn.compute.get_server(vm_id)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_vm_hypervisor_name(self,
                               vm_id : str):

        server = self.get_server(vm_id)
        return getattr(server, 'host', None)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def resources_available(self,
                            vcpus : int,
                            ram_mb : int,
                            disk_gb : int) -> bool:

        for hypervisor in self.conn.compute.v2.hypervisors(details=False):
            print(hypervisor.to_dict())

        return False