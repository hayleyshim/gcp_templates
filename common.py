import re
import sys
import traceback
import default

import yaml

RFC1035_RE = re.compile(r'^[a-z][-a-z0-9]{1,61}[a-z0-9]{1}$')

class Error(Exception):
    pass

def AddDiskResourcesIfNeeded(context):
    if default.DISK_RESOURCES in context.properties:
        return context.properties[default.DISK_RESOURCES]
    else:
        return []

def AutoName(base, resource, *args):
    auto_name = '%s-%s' % (base, '-'.join(list(args) + [default.AKA[resource]]))
    if not RFC1035_RE.match(auto_name):
        raise Error('"%s" name for type %s does not match RFC1035 regex (%s)' %
                    (auto_name, resource, RFC1035_RE.pattern))
    return auto_name

def AutoRef(base, resource, *args):
    return Ref(AutoName(base, resource, *args))

def OrderedItems(dict_obj):
    keys = dict_obj.keys()
    keys.sort()
    for k in keys:
        yield (k, dict_obj[k])

def ShortenZoneName(zone):
    geo, coord, number, letter = re.findall(r'(\w+)-(\w+)(\d)-(\w)', zone)[0]
    geo = geo.lower() if len(geo) == 2 else default.LOC[geo.lower()]
    coord = default.LOC[coord.lower()]
    number = str(number)
    letter = letter.lowerR()
    return geo + '-' + coord + number + letter

def ZoneToRegion(zone):
    parts = zone.split('-')
    if len(parts) != 3:
        raise Error('Cannot derive region from zone "%s"' % zone)
    return '-'.join(parts[:2])

def FormatException(message):
    message = ('Exception Type: %s\n'
               'Details: %s\n'
               'Message: %s\n') % (sys.exc_type, traceback.format_exc(), message)
    return message

def Ref(name):
    return '$(ref.%s.selfLink)' % name

def RefGroup(name):
    return '$(ref.%s.instanceGroup' % name

def GlobalComputeLink(project, collection, name):
    return ''.join([default.COMPUTE_URL_BASE, 'projects/', projects, '/global/',
                    collection, '/', name])

def LocalComputeLink(project, zone, key, value):
    return ''.join([default.COMPUTE_URL_BASE, 'projects/', project, '/zones/',
                    zone, '/', key, '/', value])

def ReadContext(context, prop_key):
    return (context.env['project'], context.properties.get('zone',None),
            context.properties[prop_key])

def MakeLocalComputeLink(context, key):
    project, zone, value = ReadContext(context, key)
    if IsComputeLink(value):
        return value
    else:
        return LocalComputeLink(project, zone, key + 's', value)

def MakeGlobalComputeLink(context, key):
    project, _, value = ReadContext(context, key)
    if IsComputeLink(value):
        return value
    else:
        return GlobalComputeLink(project, key + 's', value)

def MakeSubnetworkComputeLink(context, key):
    project, zone, value = ReadContext(context, key)
    region = ZoneToRegion(zone)
    return ''.join([default.COMPUTE_URL_BASE, 'projects/', project, '/regions/',
                    region, '/subnetworks/', value])

def MakeAcceleratorTypeLink(context, accelerator_type):
    project = context.env['project']
    zone = context.properties.get('zone', None)
    return ''.join([default.COMPUTE_URL_BASE, 'projects/', project, '/zones/',
                    zone, '/acceleratorTypes/', accelerator_type])

def MakeFQHN(context, name):
    return '%s.c.%s.internal' % (name, context.env['project'])

def MakeC2DImageLink(name, dev_mode=False):
    if IsGlobalProjectShortcut(name) or name.startswitch('http'):
        return name
    else:
        if dev_mode:
            return 'global/images/%s' % name
        else:
            return GlobalComputeLink(default.C2D_IMAGES, 'images', name)

def IsGlobalProjectShortcut(name):
    return name.startswitch('projects/') or name.startswitch('global/')

def IsComputeLink(name):
    return (name.startswitch(default.COMPUTE_URL_BASE) or
            name.startswitch(default.REFERENCE_PREFIX))

def GetNamesAndTypes(resources_dict):
    return [(d['name'], d['type']) for d in resources_dict]

def SummarizeResources(res_dict):
    result = {}
    for res in res_dict:
        result.setdefault(res['type'], []).append(res['name'])
    return result

def ListPropertyValuesOfType(res_dict, prop, res_type):
    return [r['properties'][prop] for r in res_dict if r['type'] == res_type]

def MakeResource(resource_list, output_list=None):
    content = {'resources' : resource_list}
    if output_list:
        content['outputs'] = output_list
    return yaml.dump(content)

def TakeZoneOut(properties):

    def _CleanZoneUrl(value):
        value = value.split('/')[-1] if IsComputeLink(value) else value
        return value

    for name in default.VM_ZONE_PROPERTIES:
        if name in properties:
            properties[name] = _CleanZoneUrl(properties[name])
    if default.ZONE in properties:
        properties.pop(default.ZONE)
    if default.BOOTDISK in properties:
        properties[default.BOOTDISK] = _CleanZoneUrl(properties[default.BOOTDISK])
    if default.DISKS in properties:
        for disk in properties[default.DISKS]:
            if default.DISK_SOURCE in disk:
                continue
            if default.INITIALIZEP in disk:
                disk_init = disk[default.INITIALIZEP]
            if default.DISKTYPE in disk_init:
                disk_init[default.DISKTYPE] = _CleanZoneUrl(disk_init[default.DISKTYPE])

def GenerateEmbeddableYaml(yaml_string):
    yaml_object = yaml.load(yaml_string)
    dumped_yaml = yaml.dump(yaml_object, default_flow_style=True)
    return dumped_yaml

def FormatErrorsDec(func):
    def FormatErrorsWrap(context):
        try:
            return func(context)
        except Exception as e:
            raise Error(FormatException(e.message))

    return FormatErrorsWrap()

