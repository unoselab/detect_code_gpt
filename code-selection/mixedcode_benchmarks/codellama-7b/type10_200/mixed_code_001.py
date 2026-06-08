def hwc_mixed_001_01(self):
        """Return a list of attribute names for the mapping.

        :rtype: list

        """
        return sorted([k for k in dir(self) if
                       k[0:1] != '_' and k != 'keys' and not k.isupper() and
                       not inspect.ismethod(getattr(self, k)) and
                       not (hasattr(self.__class__, k) and
                            isinstance(getattr(self.__class__, k),
                                       property)) and
                       not isinstance(getattr(self, k), property)]) 

def agc_mixed_001_02(self, domain, record_type, name=None, data=None):
        """
        Returns a list of all records configured for the specified domain that
        match the supplied search criteria.
        """
        if not name:
            name = ''
        if not data:
            data = ''
        return self.connection.request('domains/%s/records' % (domain),
                                       params={'type': record_type,
                                               'name': name,
                                               'data': data}).object 

def agc_mixed_001_03(self, requires):
        """Resolve pre-setup requirements"""
        build_env = self.get_finalized_command('build_ext').build_env
        for req in requires:
            if req.startswith('-'):
                continue
            try:
                dist = pkg_resources.get_distribution(req)
            except pkg_resources.DistributionNotFound:
                dist = self.distribution
                req = '%s==%s' % (req, dist.get_version())
            build_env['packages'].append(dist.project_name)
            build_env['package_dir'][dist.project_name] = dist.location
            build_env['platform'] = dist.location
            build_env['py_modules'].append(dist.project_name)
            build_env['scripts'].append(os.path.join(dist.location, dist.project_name)) 

def hwc_mixed_001_04(opaque, conn, data):
    """
    Convenience function adding common data to the event and sending it
    on the salt event bus.

    :param opaque: the opaque data that is passed to the callback.
                   This is a dict with 'prefix', 'object' and 'event' keys.
    :param conn: libvirt connection
    :param data: additional event data dict to send
    """
    tag_prefix = opaque['prefix']
    object_type = opaque['object']
    event_type = opaque['event']

    # Prepare the connection URI to fit in the tag
    # qemu+ssh://user@host:1234/system -> qemu+ssh/user@host:1234/system
    uri = urlparse(conn.getURI())
    uri_tag = [uri.scheme]
    if uri.netloc:
        uri_tag.append(uri.netloc)
    path = uri.path.strip('/')
    if path:
        uri_tag.append(path)
    uri_str = "/".join(uri_tag)

    # Append some common data
    all_data = {
        'uri': conn.getURI()
    }
    all_data.update(data)

    tag = '/'.join((tag_prefix, uri_str, object_type, event_type))

    # Actually send the event in salt
    if __opts__.get('__role') == 'master':
        salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event(all_data, tag)
    else:
        __salt__['event.send'](tag, all_data) 

def agc_mixed_001_05(self, value):
        """
        Returns a UTF-8 string representation of the parameter value,
        recursing into lists.
        """
        # Extract IDs from objects
        if isinstance(value, list):
            return '[' + ', '.join(self._process_param_value(v) for v in value) + ']'
        elif isinstance(value, dict):
            return '{' + ', '.join('%s: %s' % (k, self._process_param_value(v)) for k, v in value.items()) + '}'
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, float):
            return str(value)
        elif isinstance(value, str):
            return value
        else:
            raise TypeError('Parameter value must be str, int, float, bool, list or dict') 

def hwc_mixed_001_06(self):
        """
        Generates a dictionary of responses from a <random> element
        """
        responses = []
        for child in self._element:
            weight = int_attribute(child, 'weight', 1)
            self._log.debug('Parsing random entry with weight {weight}: {entry}'
                            .format(weight=weight, entry=child.text))

            # If the random element doesn't contain any tags, just store the text and return
            if not len(child):
                responses.append((child.text, weight))
                continue

            # Otherwise, parse all the available tags
            responses.append((tuple(self.trigger.agentml.parse_tags(child, self.trigger)), weight))
        self._responses = tuple(responses)
