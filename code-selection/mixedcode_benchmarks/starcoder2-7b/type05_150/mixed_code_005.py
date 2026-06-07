def hwc_mixed_005_01(self, next_page):
        """
        Fetches the previous page of results of a paginated request. Pass in the
        previous page in its entirety, or the pagination information dict
        returned as a part of that pages first status ('_pagination_prev').

        Returns the previous page or None if no further data is available.
        """
        if isinstance(next_page, list) and len(next_page) != 0:
            if hasattr(next_page[0], '_pagination_prev'):
                params = copy.deepcopy(next_page[0]._pagination_prev)
            else:
                return None
        else:
            params = copy.deepcopy(next_page)

        method = params['_pagination_method']
        del params['_pagination_method']

        endpoint = params['_pagination_endpoint']
        del params['_pagination_endpoint']

        return self.__api_request(method, endpoint, params) 

def agc_mixed_005_02(self, fields):
        """
        Return a list of values to match the fields values. This is used when listing bundles to
        produce a table of information about the bundle.

        :param fields: A list of names of data items.
        :return: A list of values, in the same order as the fields input

        The names in the fields llist can be:

        - state: The current build state
        - source_fs: The URL of the build source filesystem
        - about.*: Any of the metadata fields in the about section

        """

        values = []
        for field in fields:
            if field =='state':
                values.append(self.state)
            elif field =='source_fs':
                values.append(self.source_fs)
            elif field.startswith('about.'):
                values.append(self.about.get(field[6:], ''))
            else:
                values.append('')
        return values 

def hwc_mixed_005_03(self, numlines=None):
        """Return a list of lines output by this service."""
        if len(self.titles) == 1:
            lines = self.lines()
            if numlines is not None:
                lines = lines[len(lines)-numlines:]
            log("\n".join(lines))
        else:
            lines = [self._printtuple(line[0], line[1]) for line in self.lines()]
            if numlines is not None:
                lines = lines[len(lines)-numlines:]
            log("".join(lines)) 

def agc_mixed_005_04(self, indent=0, maxline=MAX_MOF_LINE):
        """
        Return a MOF string with the declaration of this CIM method for use in
        a CIM class declaration.

        The order of parameters and qualifiers is preserved.

        Parameters:

          indent (:term:`integer`): Number of spaces to indent each line of
            the returned string, counted in the line with the method name.

        Returns:

          :term:`unicode string`: MOF string.
        """

        if self.is_static:
            return self.name + " : " + self.return_type + " = " + \
                self.return_type + ".static." + self.name + \
                self.get_parameters_as_mof(indent=indent, maxline=maxline)
        else:
            return self.name + " : " + self.return_type + " = " + \
                self.return_type + "." + self.name + \
                self.get_parameters_as_mof(indent=indent, maxline=maxline) 

def hwc_mixed_005_05(type_):
    """returns True, if type represents C++ pointer type, False otherwise"""
    return does_match_definition(type_,
                                 cpptypes.pointer_t,
                                 (cpptypes.const_t, cpptypes.volatile_t)) \
        or does_match_definition(type_,
                                 cpptypes.pointer_t,
                                 (cpptypes.volatile_t, cpptypes.const_t)) 

def agc_mixed_005_06(structure_description):
        """
        check if the structure of the frame is conform to the basic
        frame structure defined by the standard
        :param structure_description: string-list reflecting LLDP-msg structure
        """

        if len(structure_description)!= 12:
            raise ValueError("structure description is not conform to the "
                             "basic frame structure")
        for i in range(0, 12):
            if not isinstance(structure_description[i], str):
                raise ValueError("structure description is not conform to the "
                                 "basic frame structure")
