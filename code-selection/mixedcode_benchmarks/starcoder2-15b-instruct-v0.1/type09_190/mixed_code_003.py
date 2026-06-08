def hwc_mixed_003_01(self):
        """Convert to the internal representation of (angstroms, photlam).
        This is for internal use only.

        """
        self.validate_units()

        savewunits = self.waveunits
        savefunits = self.fluxunits

        if hasattr(self, 'primary_area'):
            area = self.primary_area
        else:
            area = None

        angwave = self.waveunits.Convert(self.GetWaveSet(), 'angstrom')
        phoflux = self.fluxunits.Convert(angwave, self._fluxtable, 'photlam',
                                         area=area)

        self._wavetable = angwave.copy()
        self._fluxtable = phoflux.copy()

        self.waveunits = savewunits
        self.fluxunits = savefunits 

def agc_mixed_003_02(self):
        """
        Returns errors on:
        Certificate, PrivateKey or Chain not being properly formatted
        Arn not existing if its provided
        PrivateKey size > 2048
        Certificate expired or is not yet in effect

        Does not return errors on:
        Checking Certificate is legit, or a selfsigned chain is provided

        :return: str(JSON) for response
        """
        errors = []
        if not self.certificate:
            errors.append("Certificate not properly formatted")
        if not self.private_key:
            errors.append("PrivateKey not properly formatted")
        if not self.chain:
            errors.append("Chain not properly formatted")
        if self.arn and not self.certificate_manager.get_certificate(self.arn):
            errors.append("Arn not existing")
        if len(self.private_key) > 2048:
            errors.append("PrivateKey size > 2048")
        if self.certificate.not_valid_before > datetime.now() or self.certificate.not_valid_after < datetime.now():
            errors.append("Certificate expired or is not yet in effect")
        return json.dumps(errors) 

def hwc_mixed_003_03(ret, ruby, user=None):
    """
    Verify that ruby is uninstalled
    """
    ret = _ruby_installed(ret, ruby, user=user)
    if ret['result']:
        if ret['default']:
            __salt__['rbenv.default']('system', runas=user)

        if __salt__['rbenv.uninstall_ruby'](ruby, runas=user):
            ret['result'] = True
            ret['changes'][ruby] = 'Uninstalled'
            ret['comment'] = 'Successfully removed ruby'
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to uninstall ruby'
            return ret
    else:
        ret['result'] = True
        ret['comment'] = 'Ruby {0} is already absent'.format(ruby)

    return ret 

def agc_mixed_003_04(ins):
    """ Defines a memory space with a default set of bytes/words in hexadecimal
    (starting with a number) or literals (starting with #).
    Numeric values with more than 2 digits represents a WORD (2 bytes) value.
    E.g. '01' => 0, '001' => 1, 0 bytes
    Literal values starts with # (1 byte) or ## (2 bytes)
    E.g. '#label + 1' => (label + 1) & 0xFF
         '##(label + 1)' => (label + 1) & 0xFFFF
    """
    if ins.startswith('0x'):
        value = int(ins[2:], 16)
        if len(ins) == 4:
            return value & 0xFF
        elif len(ins) == 6:
            return value & 0xFFFF
        else:
            raise ValueError("Invalid hexadecimal value")
    elif ins.startswith('#'):
        if len(ins) == 2:
            return eval(ins[1:]) & 0xFF
        elif len(ins) == 3:
            return eval(ins[1:]) & 0xFFFF
        else:
            raise ValueError("Invalid literal value")
    else:
        raise ValueError("Invalid input") 

def hwc_mixed_003_05(cls, action_map=None, **initkwargs):
        """
        Allows custom request to method routing based on given ``action_map`` kwarg.
        """

        # Needs to re-implement the method but contains all the things the parent does.
        if not action_map:  # actions must not be empty
            raise TypeError("action_map is a required argument.")

        def view(request):
            self = cls(**initkwargs)
            self.request = request
            self.lookup_url_kwargs = self.request.matchdict
            self.action_map = action_map
            self.action = self.action_map.get(self.request.method.lower())

            for method, action in action_map.items():
                handler = getattr(self, action)
                setattr(self, method, handler)

            return self.dispatch(self.request, **self.request.matchdict)

        return view 

def agc_mixed_003_06(self):
        """
        Return the unicode XML snippet for the ``<c:val>`` element describing
        this series, containing the series values and their spreadsheet range
        reference.
        """
        values = self._values
        if values is None:
            values = self._values = self._series_values()
        value_xml = []
        for value in values:
            value_xml.append(
                '<c:ptCount val="{count}"/><c:numCache>{values}</c:numCache>'
               .format(
                    count=len(value),
                    values="".join(value)
                )
            )
        return "".join(value_xml)
