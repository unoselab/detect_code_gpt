def hwc_mixed_005_01(host):
    """ Put your host information in the prefix object. """
    p = new_prefix()
    p.prefix = str(host['ipaddr'])
    p.type = "host"
    p.description = host['description']
    p.node = host['fqdn']
    p.avps = {}

    # Use remaining data from ipplan to populate comment field.
    if 'additional' in host:
        p.comment = host['additional']

    # Use specific info to create extra attributes.
    if len(host['location']) > 0:
        p.avps['location'] = host['location']

    if len(host['mac']) > 0:
        p.avps['mac'] = host['mac']

    if len(host['phone']) > 0:
        p.avps['phone'] = host['phone']

    if len(host['user']) > 0:
        p.avps['user'] = host['user']

    return p 

def hwc_mixed_005_02(self, value):
        """
        Handles the following cases:
        1. If the value is already the proper type (a regex), return it.
        2. If the value is a string, compile and return the regex.

        Raises: A ValidationError if the regex cannot be compiled.
        """
        if isinstance(value, type(re.compile(''))):
            return value
        else:
            if value is None and self.null:
                return None
            else:
                try:
                    return self.get_compiled_regex(value)
                except:
                    raise ValidationError('Invalid regex {0}'.format(value)) 

def agc_mixed_005_03(self, nameformat=None, capitalize=None, formatters=None, **kwargs):
        """Pick a random name form a specified list of name parts"""

        if nameformat is None:
            nameformat = self.nameformat
        if capitalize is None:
            capitalize = self.capitalize
        if formatters is None:
            formatters = self.formatters

        if nameformat not in self.nameformats:
            raise ValueError("Unknown name format: %s" % nameformat)

        parts = self.nameformats[nameformat]
        if capitalize:
            parts = [part.capitalize() for part in parts]

        return " ".join([formatters[part](**kwargs) for part in parts]) 

def agc_mixed_005_04(self, requested_device, map_device):
        """Compare the requested device with the map device and
        return the map device if it differs from the requested device
        along with a warning.
        """
        if requested_device != map_device:
            warnings.warn(
                "The requested device '{}' is different from the "
                "mapped device '{}'. The mapped device will be used "
                "instead.".format(requested_device, map_device),
                RuntimeWarning,
            )
            return map_device
        else:
            return requested_device 

def hwc_mixed_005_05():
    """Constructs a version string of the form:

           <tag>[.<distance-from-tag>[+<branch-name-if-not-master>]]

       Master is understood to be always buildable and thus untagged
       versions are treated as patch levels. Branches not master are treated
       as PEP-440 "local version identifiers".
    """
    tag = cmd('git', 'describe').strip()
    pieces = s(tag).split('-')
    dotted = pieces[0]
    if len(pieces) < 2:
        distance = None
    else:
        # Distance from the latest tag is treated as a patch level.
        distance = pieces[1]
        dotted += '.' + s(distance)
    # Branches that are not master are treated as local:
    #   https://www.python.org/dev/peps/pep-0440/#local-version-identifiers
    if distance is not None:
        branch = get_git_branch()
        if branch != 'master':
            dotted += '+' + s(branch)
    return dotted 

def agc_mixed_005_06(self, path_spec):
    """Opens the file-like object defined by path specification.

    Args:
      path_spec (PathSpec): path specification.

    Returns:
      pyvhdi.file: a file-like object.

    Raises:
      PathSpecError: if the path specification is incorrect.
    """
    if not path_spec.HasParent():
      raise errors.PathSpecError(
          u'Missing parent in path specification: {0:s}.'.format(
              path_spec.comparable))

    parent_path_spec = path_spec.parent
    location = getattr(parent_path_spec, u'location', None)
    if location is None:
      raise errors.PathSpecError(
          u'Parent path specification missing location: {0:s}.'.format(
              parent_path_spec.comparable))

    if not path_spec.Has(u'name'):
      raise errors.PathSpecError(
          u'Path specification missing name: {0:s}.'.format(
              path_spec.comparable))

    name = path_spec.name

    file_object = self._file_system.OpenFileObject(location, name)
    return file_object
