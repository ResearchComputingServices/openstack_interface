from openstack_interface.openstack_interface import OpenStackInterface

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def test_change_project():

    openstack_interface = OpenStackInterface()

    project_name_good = "Science"
    project_name_bad = "NonExistentProject"

    try:
        openstack_interface.change_project(project_name=project_name_bad)
    except ValueError as e:
        print(e)

    try:
        openstack_interface.change_project(project_name=project_name_good)
    except ValueError as e:
        print(e)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():

    openstack_interface = OpenStackInterface()
    vm = None
    fip = None

    project_name_good = "Science"
    project_name_bad = "NonExistentProject"
    vm_name_good = "sci-test-0"
    vm_name_bad = "non-existent-vm"

    try:
        vm = openstack_interface.get_vm(vm_name=vm_name_bad)
    except ValueError as e:
        print(e)

    try:
        vm = openstack_interface.get_vm(vm_name=vm_name_good)
        print(f"Found VM: {vm.name} with ID: {vm.id}")
    except ValueError as e:
        print(e)

    try:
        print("Attach Floating IP to VM...")
        openstack_interface.attach_fip_to_vm(vm=vm)
    except Exception as e:
        print(e)

    input("Press Enter to detach the floating IP...")

    try:
        print("Detaching Floating IP from VM...")
        openstack_interface.detach_fip_from_vm(vm=vm)
    except Exception as e:
        print(e)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == "__main__":
    main()