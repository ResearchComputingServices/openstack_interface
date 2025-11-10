#!/usr/bin/env python3
"""
Test script to verify the OpenStack SDK migration works correctly.
This replaces the individual OpenStack clients with the unified SDK.
"""

import os
import sys
from unittest.mock import Mock, patch

# Add the openstack_interface module to the path
sys.path.insert(0, '/home/sysadmin/CloudMan/openstack_interface')

try:
    from openstack_interface.openstack_interface import OpenStackInterface
    print("✓ Successfully imported OpenStackInterface")
except ImportError as e:
    print(f"✗ Failed to import OpenStackInterface: {e}")
    sys.exit(1)

def test_initialization():
    """Test that the class can be initialized with OpenStack SDK."""

    # Mock environment variables
    env_vars = {
        'OS_USERNAME': 'test_user',
        'OS_PASSWORD': 'test_password',
        'OS_AUTH_URL': 'http://test:5000/v3',
        'OS_PROJECT_NAME': 'test_project',
        'OS_PROJECT_DOMAIN_NAME': 'default',
        'OS_USER_DOMAIN_NAME': 'default',
        'OS_CACERT': '/path/to/cert'
    }

    with patch.dict(os.environ, env_vars):
        with patch('openstack.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            try:
                interface = OpenStackInterface(
                    vm_setup_script_path='/tmp/vm_setup.sh',
                    gpu_setup_script_path='/tmp/gpu_setup.sh',
                    monitor_setup_script_path='/tmp/monitor_setup.sh'
                )
                print("✓ Successfully initialized OpenStackInterface with OpenStack SDK")

                # Verify the connection was created with correct parameters
                mock_connect.assert_called_once_with(
                    auth_url='http://test:5000/v3',
                    project_name='test_project',
                    username='test_user',
                    password='test_password',
                    project_domain_name='default',
                    user_domain_name='default',
                    verify='/path/to/cert'
                )

                # Verify the connection is stored
                assert interface.conn == mock_conn
                print("✓ Connection properly stored in interface")

            except Exception as e:
                print(f"✗ Failed to initialize interface: {e}")
                return False

    return True

def test_project_switching():
    """Test that project switching works with the new SDK."""

    env_vars = {
        'OS_USERNAME': 'test_user',
        'OS_PASSWORD': 'test_password',
        'OS_AUTH_URL': 'http://test:5000/v3',
        'OS_PROJECT_NAME': 'test_project',
        'OS_PROJECT_DOMAIN_NAME': 'default',
        'OS_USER_DOMAIN_NAME': 'default',
        'OS_CACERT': '/path/to/cert'
    }

    with patch.dict(os.environ, env_vars):
        with patch('openstack.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            interface = OpenStackInterface(
                vm_setup_script_path='/tmp/vm_setup.sh',
                gpu_setup_script_path='/tmp/gpu_setup.sh',
                monitor_setup_script_path='/tmp/monitor_setup.sh'
            )

            # Test switching projects
            interface._switch_project('new_project')

            # Should have been called twice - once for init, once for switch
            assert mock_connect.call_count == 2

            # Check the second call was with the new project
            second_call = mock_connect.call_args_list[1]
            assert second_call[1]['project_name'] == 'new_project'

            print("✓ Project switching works correctly")

    return True

def main():
    """Run all tests."""
    print("Testing OpenStack SDK migration...")
    print("=" * 50)

    tests = [
        test_initialization,
        test_project_switching,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")

    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! OpenStack SDK migration successful.")
        return 0
    else:
        print("❌ Some tests failed. Check the implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(main())