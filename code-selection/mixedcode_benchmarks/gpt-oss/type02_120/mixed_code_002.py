def agc_mixed_002_01(self):
        """
        Return all the resources which this function refer to.

        :return: resources
        :rtype: list

        .. seealso:: :class:`odps.models.Resource`
        """

        try:
            return self._resources
        except AttributeError:
            resources = []
            obj = getattr(self, "_obj", None)
            if isinstance(obj, dict):
                for r in obj.get("Resources", []):
                    name 

def hwc_mixed_002_02(element, msg):
        """process_attrib

        High-level api: Delete four attributes from an ElementTree node if they
        exist: operation, insert, value and key. Then a new attribute 'diff' is
        added.

        Parameters
        ----------

        element : `Element`
            A node needs to be looked at.

        msg : `str`
            Message to be added in attribute 'diff'.

        Returns
        -------

        Element
            Argument 'element' is returned after processing.
        """

        attrib_required = ['type', 'access', 'mandatory']
        for node in element.iter():
            for attrib in node.attrib.keys():
                if attrib not in attrib_required:
                    del node.attrib[attrib]
            if msg:
                node.attrib['diff'] = msg
        return element 

def agc_mixed_002_03(self):
        """
        Test if a node is not linking to any fan in or out node.
        """
        fan_in = getattr(self, "fan_in", None)
        fan_out = getattr(self, "fan_out", None)

        if fan_in is None and fan_out is None:
            return True
        if fan_in is None:
            return not bool(fan_out)
        if fan_out is None:
            return not bool(fan_in)

        return not bool(fan_in) and not bool(fan_out) 

def hwc_mixed_002_04(type_func, minimum, maximum):
    """
    Require variables to be of the specified type, between minimum and maximum
    """
    @functools.wraps(type_func)
    def inner(string):
        result = type_func(string)
        if not result >= minimum and result <= maximum:
            raise argparse.ArgumentTypeError(
                    "Please provide a value between {0} and {1}".format(
                        minimum, maximum))
        return result
    return inner 

def agc_mixed_002_05(self):
        """
        Kills old session and creates a new one with no proxies or headers
        """
        # Kill old connection
        try:
            sess = getattr(self, "session", None)
            if sess is not None:
                sess.close()
        finally:
            import requests
            self.session = requests.Session()
            self.session.proxies = {}
            self.session.headers.clear() 

def hwc_mixed_002_06(self, data, original_data):
        """Check for unknown keys."""
        if isinstance(original_data, list):
            for elem in original_data:
                self.load_unknown_fields(data, elem)
        else:
            for key, value in original_data.items():
                if key not in data:
                    data[key] = value
        return data
