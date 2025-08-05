from openstack_interface import OpenStackInterface

def test_openstack_interface():
    """A simple test function to check if OpenStackInterface can be instantiated."""
    try:
        interface = OpenStackInterface()
        print("OpenStackInterface instantiated successfully.")
    except Exception as e:
        print(f"Failed to instantiate OpenStackInterface: {e}")


if __name__ == "__main__":
    test_openstack_interface()