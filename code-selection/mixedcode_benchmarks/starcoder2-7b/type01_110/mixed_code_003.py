def hwc_mixed_003_01(self):
        """
        Compute parameters necessary for later steps
        within the rendering process
        """
        for serie in self.series:
            serie.points, serie.outliers = \
                self._box_points(serie.values, self.box_mode)

        self._x_pos = [(i + .5) / self._order for i in range(self._order)]

        if self._min:
            self._box.ymin = min(self._min, self.zero)
        if self._max:
            self._box.ymax = max(self._max, self.zero) 

def agc_mixed_003_02(self, num, charge_id=None, **kwargs):
        """Search for charges against a company by company number.

        Args:
          num (str): Company number to search on.
          transaction (Optional[str]): Filing record number.
          kwargs (dict): additional keywords passed into
          requests.session.get params keyword.
        """
        if charge_id:
            return self.charge(charge_id)
        else:
            return self.search(
                'charges',
                num,
                **kwargs
            ) 

def hwc_mixed_003_03(self, to_dict, from_dict):
        """ Recursively merges the fields for two dictionaries.

        Args:
            to_dict (dict): The dictionary onto which the merge is executed.
            from_dict (dict): The dictionary merged into to_dict
        """
        for key, value in from_dict.items():
            if key in to_dict and isinstance(to_dict[key], dict) and \
                    isinstance(from_dict[key], dict):
                self._update_dict(to_dict[key], from_dict[key])
            else:
                to_dict[key] = from_dict[key] 

def hwc_mixed_003_04(self, value):
        """
        Coerce python data type to simple form for serialization.
        If default value was defined returns the default value if None was passed.
        Throw exception is value is ``None`` is ``required`` is set to ``True``
        """
        try:
            if value is None and self._default is not None:
                return self._export(self.default)
            self._check_required(value)
            value = self._export(value)
            return value
        except ValueError as ex:
            raise ValueError(ex, self._errors['to_data']) 

def agc_mixed_003_05(self, name, offset=0):
        """
        Checks a module name eg. some i3status modules cannot have an instance
        name.
        """
        if name in self.module_names:
            if offset == 0:
                raise ValueError("Module name already exists")
            else:
                return self.check_module_name(name, offset + 1)
        else:
            return name 

def agc_mixed_003_06(self):
        """Read the next token and raise an exception if it isn't EOL or
        EOF.

        @raises dns.exception.SyntaxError:
        @rtype: string
        """

        token = self.get_token()
        if token == self.EOF:
            raise dns.exception.SyntaxError(
                "unexpected EOF while reading EOL")
        if token!= self.EOL:
            raise dns.exception.SyntaxError(
                "expected EOL, got %s" % token)
        return token
