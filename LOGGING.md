# OpenStackInterface Logging

The OpenStackInterface class now includes comprehensive logging throughout its operations.

## Logger Name

`cloudman.app.openstack`

## Logged Operations

### Initialization
- Session creation
- Client initialization
- Project list loading
- VM setup script loading

### Project Management
- Project switching
- Project validation

### Floating IP Operations
- Allocation
- Association/disassociation
- Release
- Availability checks

### VM Operations
- VM creation (including status polling)
- VM lookup by name
- VM lookup by floating IP
- Port ID retrieval
- Hypervisor name retrieval

### Network Operations
- Network ID lookup
- Network list operations

### Image Operations
- Image list retrieval
- Image lookup by name

## Log Levels Used

- **DEBUG**: Detailed operations (lookups, status checks, intermediate steps)
- **INFO**: Major operations (VM creation, project switching, FIP operations)
- **WARNING**: Expected issues (VM not found, no FIPs available)
- **ERROR**: Unexpected failures (allocation errors, VM errors)

## Integration

Since this logger uses the standard Python logging hierarchy (`cloudman.app.openstack`), it inherits settings from the parent `cloudman.app` logger configured in the CloudManApp logging setup. All logs are written to `logs/api/cloudman_app.log`.

## Example Log Output

```
2025-12-08 14:30:15 - cloudman.app.openstack - INFO - Initializing OpenStackInterface
2025-12-08 14:30:15 - cloudman.app.openstack - DEBUG - External network ID: bb005c60-fb45-481a-97fb-f746033e1c5d
2025-12-08 14:30:16 - cloudman.app.openstack - INFO - OpenStackInterface initialized with 5 projects
2025-12-08 14:30:20 - cloudman.app.openstack - INFO - Creating VM: hostname=science-smith-gpu-0, project=science, flavor=4cpu16gb.100g
2025-12-08 14:30:20 - cloudman.app.openstack - INFO - Switching to project: science
2025-12-08 14:30:21 - cloudman.app.openstack - DEBUG - Requesting VM creation from Nova: hostname=science-smith-gpu-0, image=Ubuntu 22.04
2025-12-08 14:30:25 - cloudman.app.openstack - DEBUG - Waiting for VM science-smith-gpu-0 to become ACTIVE. Current status: BUILD
2025-12-08 14:30:45 - cloudman.app.openstack - INFO - VM science-smith-gpu-0 is now ACTIVE
2025-12-08 14:30:45 - cloudman.app.openstack - INFO - Attaching floating IP to VM: science-smith-gpu-0
2025-12-08 14:30:46 - cloudman.app.openstack - INFO - Successfully attached floating IP 192.168.1.100 to VM: science-smith-gpu-0
```
