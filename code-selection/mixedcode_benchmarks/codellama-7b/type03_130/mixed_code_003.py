def agc_mixed_003_01(obj_map):
    """converts string representations of _id back to ObjectId obj"""
    for key, value in obj_map.items():
        if key == "_id":
            obj_map[key] = ObjectId(value)
        elif isinstance(value, dict):
            obj_map[key] = convert_ids_to_object_ids(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    obj_map[key] = convert_ids_to_object_ids(item)
    return obj_map 

def agc_mixed_003_02(group, groups, users):
    """
    Gather group members
    """
    group_members = []
    for member in group.members:
        if member.type == 'user':
            group_members.append(member.id)
        elif member.type == 'group':
            group_members.append(member.id)
            if member.id not in groups:
                groups[member.id] = _gather_group_members(member, groups, users)
        else:
            raise Exception('Unknown member type: %s' % member.type)
    return group_members 

def agc_mixed_003_03(self, k:int, max_len:int=70)->None:
        """
        Create a tabulation showing the first `k` texts in top_losses along with their prediction, actual,loss, and probability of
        actual class. `max_len` is the maximum number of tokens displayed.
        """
        if k>len(self.top_losses):
            k=len(self.top_losses)
        for i in range(k):
            print(f"{i+1:>2d}. {self.top_losses[i][0][:max_len]}")
            print(f"    Prediction: {self.top_losses[i][1]}")
            print(f"    Actual: {self.top_losses[i][2]}")
            print(f"    Loss: {self.top_losses[i][3]:.4f}")
            print(f"    Probability: {self.top_losses[i][4]:.4f}")
            print() 

def hwc_mixed_003_04(self):
        """
        Determines how to convert CDF byte ordering to the system
        byte ordering.
        """

        if sys.byteorder == 'little' and self._endian() == 'big-endian':
            # big->little
            order = '>'
        elif sys.byteorder == 'big' and self._endian() == 'little-endian':
            # little->big
            order = '<'
        else:
            # no conversion
            order = '='
        return order 

def hwc_mixed_003_05(self, **kwargs):
        """Auto Generated Code
        """
        config = ET.Element("config")
        show_portindex_interface_info = ET.Element("show_portindex_interface_info")
        config = show_portindex_interface_info
        output = ET.SubElement(show_portindex_interface_info, "output")
        show_portindex_interface = ET.SubElement(output, "show-portindex-interface")
        portsgroup_rbridgeid_key = ET.SubElement(show_portindex_interface, "portsgroup-rbridgeid")
        portsgroup_rbridgeid_key.text = kwargs.pop('portsgroup_rbridgeid')
        show_portindex = ET.SubElement(show_portindex_interface, "show-portindex")
        port_index = ET.SubElement(show_portindex, "port-index")
        port_index.text = kwargs.pop('port_index')

        callback = kwargs.pop('callback', self._callback)
        return callback(config) 

def hwc_mixed_003_06(package='', cyg_arch='x86_64'):
    """
    List locally installed packages.

    package : ''
        package name to check. else all

    cyg_arch :
        Cygwin architecture to use
        Options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.list
    """
    pkgs = {}
    args = ' '.join(['-c', '-d', package])
    stdout = _cygcheck(args, cyg_arch=cyg_arch)
    lines = []
    if isinstance(stdout, six.string_types):
        lines = salt.utils.stringutils.to_unicode(stdout).splitlines()
    for line in lines:
        match = re.match(r'^([^ ]+) *([^ ]+)', line)
        if match:
            pkg = match.group(1)
            version = match.group(2)
            pkgs[pkg] = version
    return pkgs
