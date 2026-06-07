def hwc_mixed_005_01(self):
        """Yield all packages, modules, and extension names in distribution"""

        for pkg in self.packages or ():
            yield pkg

        for module in self.py_modules or ():
            yield module

        for ext in self.ext_modules or ():
            if isinstance(ext, tuple):
                name, buildinfo = ext
            else:
                name = ext.name
            if name.endswith('module'):
                name = name[:-6]
            yield name 

def hwc_mixed_005_02(self, path, data):
        """
        Generic POST with headers
        """
        uri = self.config.get_target() + path
        headers = self._post_headers()

        logging.debug("URI=POST " + str(uri))
        logging.debug("HEADERS=" + str(headers))
        logging.debug("BODY=" + str(data))

        response = self.session.post(uri, headers=headers,
                data=json.dumps(data))
        if response.status_code in (200, 201, 202):
            return response.json()
        elif response.status_code == 401:
            raise predix.admin.cf.config.CloudFoundryLoginError('token invalid')
        else:
            logging.debug("STATUS=" + str(response.status_code))
            logging.debug("CONTENT=" + str(response.content))
            response.raise_for_status() 

def agc_mixed_005_03(self, arg):
        """
        Usage:
          server on
          server off
          server restart
          server log
          server help
        """
        if arg == 'on':
            self.server.start()
            print('Server started')
        elif arg == 'off':
            self.server.stop()
            print('Server stopped')
        elif arg =='restart':
            self.server.restart()
            print('Server restarted')
        elif arg == 'log':
            self.server.log()
        elif arg == 'help':
            print('Usage: server on|off|restart|log|help')
        else:
            print('Unknown command') 

def agc_mixed_005_04(self, publisher_id, event_type_id):
        """GetEventType.
        Get a specific event type.
        :param str publisher_id: ID for a publisher.
        :param str event_type_id:
        :rtype: :class:`<EventTypeDescriptor> <azure.devops.v5_0.service_hooks.models.EventTypeDescriptor>`
        """
        route_values = {}
        if publisher_id is not None:
            route_values['publisherId'] = self._serialize.url('publisher_id', publisher_id,'str')
        if event_type_id is not None:
            route_values['eventType'] = self._serialize.url('event_type_id', event_type_id,'str')
        response = self._send(http_method='GET',
                              location_id='15980049-5400-4565-919d-878909617300',
                              version='5.0-preview.1',
                              route_values=route_values)
        return self._deserialize('EventTypeDescriptor', response) 

def hwc_mixed_005_05(self, coors, node_low_or_high=None):
        """
        Add new nodes at the end of the list.
        """
        last = self.lastnode
        if type(coors) is nm.ndarray:
            if len(coors.shape) == 1:
                coors = coors.reshape((1, coors.size))

            nadd = coors.shape[0]
            idx = slice(last, last + nadd)
        else:
            nadd = 1
            idx = self.lastnode
        right_dimension = coors.shape[1]
        self.nodes[idx, :right_dimension] = coors
        self.node_flag[idx] = True
        self.lastnode += nadd
        self.nnodes += nadd 

def agc_mixed_005_06(cookie_string, strict_cookies=False):
    """Parser for HTTP header set-cookie
    The return from this function will be used as parameters for
    django's response.set_cookie method. Because set_cookie doesn't
    have parameter comment, this cookie attribute will be ignored.

    :param  cookie_string: A string representing a valid cookie
    :param  strict_cookies: Whether to only accept RFC-compliant cookies
    :returns: A dictionary containing the cookie_string attributes
    """

    cookie = {}
    for cookie_part in cookie_string.split(';'):
        cookie_part = cookie_part.strip()
        if not cookie_part:
            continue
        if '=' not in cookie_part:
            if strict_cookies:
                raise ValueError('Invalid cookie: %s' % cookie_part)
            else:
                cookie[cookie_part] = True
                continue
        name, value = cookie_part.split('=', 1)
        name, value = name.strip(), value.strip()
        cookie[name] = value
    return cookie
