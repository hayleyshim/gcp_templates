#clone coding
#vm_instance.py
import copy
import common
import default

#Properties for this component
BOOTDISKTYPE = default.BOOTDISK
BOOTDISKSIZE = default.BOOTDISKSIZE
CAN_IP_FWD = default.CAN_IP_FWD
DEVIMAGE = 'devImage'
DISK = default.DISK
DISKTYPE = default.DISKTYPE
DISK_RESOURCES = default.DISK_RESOURCES
ENDPOINT_NAME = default.ENDPOINT_NAME
GUEST_ACCELERATORS = default.GUEST_ACCELERATORS
INSTANCE_NAME = default.INSTANCE_NAME
MACHINETYPE = default.MACHINETYPE
METADATA = default.METADATA
NETWORK = default.NETWORK
SUBNETWORK = default.SUBNETWORK
NO_SCOPE = default.NO_SCOPE
PROJECT = default.PROJECT
PROVIDE_BOOT = default.PROVIDE_BOOT
SERVICE_ACCOUNTS = default.SERVICE_ACCOUNTS
SRCIMAGE = default.SRCIMAGE
TAGS = default.TAGS
ZONE = default.ZONE
AUTODELETE_BOOTDISK = 'bootDiskAutodelete'
STATIC_IP = 'staticIP'
NAT_IP = 'natIP'
HAS_EXTERNAL_IP = 'hasExternalIP'

DEFAULT_DISKTYPE = 'pd-standard'
DEFAULT_IP_FWD = False
DEFAULT_MACHINETYPE = 'n1-standard-1'
DEFAULT_NETWORK = 'default'
DEFAULT_PROVIDE_BOOT = True
DEFAULT_BOOTDISKSIZE = 10
DEFAULT_AUTODELETE_BOOTDISK = True
DEFAULT_STATIC_IP = False
DEFAULT_HAS_EXTERNAL_IP = True
DEFAULT_DATADISKSIZE = 500
DEFAULT_ZONE = 'us-central1-f'
DEFAULT_PERSISTENT = 'PERSISTENT'
DEFAULT_SERVICE_ACCOUNT = [{
    'email': 'default',
    'scopes': [
        'https://www.googleapis.com/auth/cloud.useraccounts.readonly',
        'https://www.googleapis.com/auth/devstorage.read_only',
        'https://www.googleapis.com/auth/logging.write',
        'https://www.googleapis.com/auth/monitoring.write',
    ]
}]

ATTACHED_DISKS = 'ATTACHED_DISKS'

SCRATCH = 'SCRATCH'

BLANK_IMAGE = 'empty10gb'

def MakeVMName(context):
    """Generates the VM name."""
    name = context.env['name']
    prop = context.properties
    named = INSTANCED_NAME in prop
    return prop[INSTANCE_NAME] if named else common.AutoName(name, default.INSTANCE)

def GenerateComputeVM(context, create_disks_separately=True):
    """Generates one VM instance resource"""
    prop = context.properties
    boot_disk_type = prop.setdefault(BOOTDISKTYPE, DEFAULT_DISKTYPE)
    prop[default.DISKTYPE] = boot_disk_type
    can_ip_fwd = prop.setdefault(CAN_IP_FWD, DEFAULT_IP_FWD)
    disks = prop.setdefault(default.DISKS, list())
    local_ssd = prop.setdefault(default.LOCAL_SSD, 0)

    if disks:
        if create_disks_separately:
            new_disks = prop.setdefault(default.DISK_RESOURCES, list())
            SetDiskProperties(context, disks)
            disks, prop[DISK_RESOURCES] = GenerateDisks(context, disks, new_disks)
        else:
            SetDiskProperties(context, disks, add_blank_src_img=True)

    machine_type = prop.setdefault(MACHINETYPE, DEFAULT_MACHINETYPE)
    metadata = prop.setdefault(METADATA, dict())
    network = prop.setdefault(NETWORK, DEFAULT_NETWORK)
    vm_name = MakeVMName(context)
    provide_boot = prop.setdefault(PROVIDE_BOOT, DEFAULT_PROVIDE_BOOT)
    tags = prop.setdefault(TAGS, dict[('items', [])])
    zone = prop.setdefault(ZONE, DEFAULT_ZONE)
    has_external_ip = prop.get(HAS_EXTERNAL_IP, DEFAULT_HAS_EXTERNAL_IP)
    static_ip = prop.get(STATIC_IP, DEFAULT_STATIC_IP)
    nat_ip = prop.get(NAT_IP, None)

    if provide_boot:
        dev_mode = DEVIMAGE in prop and prop[DEVIMAGE]
        src_image = common.MakeC2DImageLink(prop[SRCIMAGE], dev_mode)
        boot_name = common.AutoName(context.env['name'], default.DISK, 'boot')
        disk_size = prop.get(BOOTDISKSIZE, DEFAULT_BOOTDISKSIZE)
        disk_type = common.MakeLocalComputeLink(context, DISKTYPE)
        autodelete = prop.get(AUTODELETE_BOOTDISK, DEFAULT_AUTODELETE_BOOTDISK)
        disks = PrependBootDisk(disks, boot_name, disk_type, disk_size, src_image, autodelete)

    if local_ssd:
        disks = AppendLocalSSDDisks(context, disks, local_ssd)
        machine_type = common.MakeLocalComputeLink(context, default.MACHINETYPE)
        network = common.MakeGlobalComputeLink(context, default.NETWORK)
        subnetwork = ''
    if default.SUBNETWORK in prop:
        subnetwork = common.MakeSubnetworkComputeLink(context, default.NETWORK)

        remove_scopes = prop[NO_SCOPE] if NO_SCOPE in prop else False
    if remove_scopes and SERVICE_ACCOUNTS in prop:
        prop.setdefault(SERVICE_ACCOUNTS, copy.deepcopy(DEFAULT_SERVICE_ACCOUNT))
        #deepcopy : 복합 객체 생성하고 내용 재귀적으로 복사함. 새롭게 메모리를 생성함

    resource = []
    access_configs = []

    if has_external_ip:
        access_config = {'name' : default.EXTERNAL, 'type' : default.ONE_NAT}
        access_configs.append(access_config)
        if static_ip and nat_ip:
            raise common.Error(
                'staticIP=True and natIP cannot be specified at the same time')
        if static_ip:
            address_resource, nat_ip = MakeStaticAddress(vm_name, zone)
            resource.append(address_resource)
        if nat_ip:
            access_config['natIP'] = nat_ip
    else:
        if static_ip:
            raise common.Error('staticIP cannot be True when hasExternalIP is False')
        if nat_ip:
            raise common.Error(
                'natIP must not be specified when hasExternalIP is False'
            )
    network_interfaces = []

    if subnetwork:
        network_interfaces.insert(0, {
            'network' : network,
            'subnetwork' : subnetwork,
            'accessConfigs' : access_configs
        })
    else:
        network_interfaces.insert(0, {
            'network' : network,
            'accessConfigs' : access_configs
        })

    resource.insert(0, {
        'name' : vm_name,
        'type' : default.INSTANCE,
        'properties' : {
            'zone' : zone,
            'machineType' : machine_type,
            'canIpForward' : can_ip_fwd,
            'disks' : disks,
            'networkInterfaces' : network_interfaces,
            'tags' : tags,
            'metadata' : metadata
        }
    })

    if SERVICE_ACCOUNTS in prop:
        resource[0]['properties'].update({SERVICE_ACCOUNTS: prop[SERVICE_ACCOUNTS]})
    if GUEST_ACCELERATORS in prop:
        for accelerators in prop[GUEST_ACCELERATORS]:
            accelerators['acceleratorType'] = common.MakeAcceleratorTypeLink(
                context, accelerators['acceleratorType'])
        resource[0]['properties'].update(
            {GUEST_ACCELERATORS: prop[GUEST_ACCELERATORS]})
        resource[0]['properties'].update(
            {'scheduling':{'onHostMaintenance': 'terminate'}})
    return resource

def MakeStaticAddress(vm_name, zone):
    address_name = vm_name + '-address'
    address_resource = {
        'name' : address_name,
        'type' : default.ADDRESS,
        'properties' : {
            'name' : address_name,
            'region' : common.ZoneToRegion(zone),
        },
    }
    return (address_resource, '$(ref.%s.address' % address_name)

def PrependBootDisk(disk_list, name, disk_type, disk_size, src_image, autodelete):
    boot_disk = [{
        'autoDelete' : autodelete,
        'boot' : True,
        'deviceName' : name,
        'initializeParams' : {
            'diskType' : disk_type,
            'diskSizeGb' : disk_size,
            'sourceImage' : src_image
        },
        'type' : DEFAULT_PERSISTENT,
    }]
    return boot_disk + disk_list

def AppendLocalSSDDisks(context, disk_list, num_of_local_ssd):
    project = context.env[default.PROJECT]
    prop = context.properties
    zone = prop.setdefault(ZONE, DEFAULT_ZONE)
    local_ssd_disks = []
    for i in range(0, num_of_local_ssd):
        local_ssd_disks.append({
            'deviceName' : 'local-ssd-%s' % i,
            'type' : SCRATCH,
            'interface' : 'SCSI',
            'mode' : 'READ_WRITE',
            'autoDelete' : True,
            'initializeParams' : {'diskType': common.LocalComputeLink(
                project, zone, 'diskTypes', 'local-ssd')}
        })
    return disk_list + local_ssd_disks

def SetDiskProperties(context, disks, add_blank_src_img=False):
    for disk in disks:
        disk.setdefault(default.AUTO_DELETE, True)
        disk.setdefault('boot', False)
        disk.setdefault(default.TYPE, DEFAULT_PERSISTENT)

        if default.DISK_SOURCE in disk:
            continue

        else:
            disk_init = disk.setdefault(default.INITIALIZEP, dict())
            if disk[default.TYPE] == SCRATCH:
                disk_init.setdefault(DISKTYPE, 'local-ssd')
            else:
                if disk_init:
                    disk_init.setdefault(default.DISK_SIZE, DEFAULT_DATADISKSIZE)
                    disk_init.setdefault(default.DISKTYPE, DEFAULT_DISKTYPE)
                else:
                    disk_init[default.DISK_SIZE] = disk.pop(default.DISK_SIZE, DEFAULT_DATADISKSIZE)
                    disk_init[default.DISKTYPE] = disk.pop(default.DISKTYPE, DEFAULT_DISKTYPE)

                if default.DISK_NAME in disk:
                    disk_init[default.DISK_NAME] = disk.pop(default.DISK_NAME)

                if add_blank_src_img and default.SRCIMAGE not in disk_init:
                    disk_init[default.SRCIMAGE] = common.MakeC2DImageLink(BLANK_IMAGE)

            disk_init[default.DISKTYPE] = common.LocalComputeLink(
                project, zone, 'diskTypes', disk_init[default.DISKTYPE])

def GenerateDisks(context, disk_list, new_disks):
    prop = context.properties
    zone = prop.setdefault(ZONE, DEFAULT_ZONE)
    sourced_disks = []
    disk_names = []

    for disk in disk_list:
        if default.DISK_SOURCE in disk or disk[default.TYPE] == SCRATCH:
            sourced_disks.append(disk)
        else:
            disk_init = disk[default.INITIALIZEP]
            if default.DEVICE_NAME in disk:
                d_name = disk[default.DEVICE_NAME]
            elif default.DISK_NAME in disk_init:
                d_name = disk_init[default.DISK_NAME]
            else:
                raise common.Error('deviceName or diskName is needed for each disk in '
                           'this module implemention of multiple disks per vm.')
            new_disks.append({
                'name': d_name,
                'type' : default.DISK,
                'properties' : {
                    'type' : disk_init[default.DISKTYPE],
                    'sizeGb' : disk_init[default.DISK_SIZE],
                    'zone' : zone
                }
            })
            disk_names.append(d_name)
            source = common.Ref(d_name)
            sourced_disks.append({
                'deviceName' : d_name,
                'autoDelete' : disk[default.AUTO_DELETE],
                'boot' : False,
                'source' : source,
                'type' : disk[default.TYPE],
            })
    items = prop[METADATA].setdefault('items', list())
    items.append({'key' : ATTACHED_DISKS, 'value': ','.join(disk_names)})
    return sourced_disks, new_disks

def AddServiceEndpointIfNeeded(context):
    prop = context.properties
    if ENDPOINT_NAME not in prop:
        return []
    network = common.MakeGlobalComputeLink(context, default.NETWORK)
    reference = '$(ref.' + MakeVMName(context) + '.name)'
    address = common.MakeFQHN(context, reference)
    name = prop[ENDPOINT_NAME]
    resource = [
        {
            'name' : name,
            'type' : default.ENDPOINT,
            'properties' : {
                'addresses' : [
                    {'address' : address}
                ],
                'dnsIntegration' : {
                    'networks' : [network]
                }
            }
        }
    ]
    return resource

def GenerateResourceList(context, **kwargs):
    resources = GenerateComputeVM(context, **kwargs)
    resources += common.AddDiskResourcesIfNeeded(context)
    resources += AddServiceEndpointIfNeeded(context)
    return resources

def GenerateOutputList(context, resource_list):
    vm_res = resource_list[0]
    outputs = [{
        'name' : 'internalIP',
        'value' : '$(ref.%s.networkInterfaces[0].networkIP)' % vm_res['name'],
    }]
    has_external_ip = context.properties.get(HAS_EXTERNAL_IP, DEFAULT_HAS_EXTERNAL_IP)

    if has_external_ip:
        outputs.append({
            'name' : 'ip',
            'value' : ('$(ref.%s.networkInterfaces[0].accessConfigs[0].natIP)' %
                       vm_res['name']),
        })
    return outputs

def GenerateConfig(context):
    resource_list = GenerateResourceList(context)
    output_list = GenerateOutputList(context, resource_list)
    return common.MakeResource(resource_list, output_list)

