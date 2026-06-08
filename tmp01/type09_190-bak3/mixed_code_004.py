def hwc_mixed_004_01(self, channel, value, unit='A'):
        """Setting current of current source
        """
        dac_offset = self._ch_cal[channel]['DAC']['offset']
        dac_gain = self._ch_cal[channel]['DAC']['gain']
        if unit == 'raw':
            value = value
        elif unit == 'A':
            value = int((-value * 1000000 - dac_offset) / dac_gain)  # fix sign of output
        elif unit == 'mA':
            value = int((-value * 1000 - dac_offset) / dac_gain)  # fix sign of output
        elif unit == 'uA':
            value = int((-value - dac_offset) / dac_gain)  # fix sign of output
        else:
            raise TypeError("Invalid unit type.")

        self._set_dac_value(channel=channel, value=value) 

def agc_mixed_004_02(id):
    """ Returns a group from the DCOS Enterprise.  It returns None if none exists.

        :param id: group id
        :type id: str
        :return: Group
        :rtype: dict
    """
    groups = {
        "group1": {
            "id": "group1",
            "description": "Group 1",
            "users": ["user1", "user2"],
            "groups": ["group2"],
        },
        "group2": {
            "id": "group2",
            "description": "Group 2",
            "users": ["user3"],
            "groups": [],
        },
    }
    if id in groups:
        return groups[id]
    else:
        return None 

def hwc_mixed_004_03(ins):
    """ Defines a memory space with a default set of bytes/words in hexadecimal
    (starting with a number) or literals (starting with #).
    Numeric values with more than 2 digits represents a WORD (2 bytes) value.
    E.g. '01' => 0, '001' => 1, 0 bytes
    Literal values starts with # (1 byte) or ## (2 bytes)
    E.g. '#label + 1' => (label + 1) & 0xFF
         '##(label + 1)' => (label + 1) & 0xFFFF
    """
    output = []
    output.append('%s:' % ins.quad[1])

    q = eval(ins.quad[2])

    for x in q:
        if x[0] == '#':  # literal?
            size_t = 'W' if x[1] == '#' else 'B'
            output.append('DEF{0} {1}'.format(size_t, x.lstrip('#')))
            continue

        # must be an hex number
        x = x.upper()
        assert RE_HEXA.match(x), 'expected an hex number, got "%s"' % x
        size_t = 'B' if len(x) <= 2 else 'W'
        if x[0] > '9':  # Not a number?
            x = '0' + x
        output.append('DEF{0} {1}h'.format(size_t, x))

    return output 

def hwc_mixed_004_04(amount_w: int,
                       entropy_w: Union[int, float],
                       entropy_n: Union[int, float],
                       amount_n: int) -> float:
    """Calculate the entropy of a passphrase with given words and numbers."""
    if not isinstance(amount_w, int):
        raise TypeError('amount_w can only be int')
    if not isinstance(entropy_w, (int, float)):
        raise TypeError('entropy_w can only be int or float')
    if not isinstance(entropy_n, (int, float)):
        raise TypeError('entropy_n can only be int or float')
    if not isinstance(amount_n, int):
        raise TypeError('amount_n can only be int')
    if amount_w < 0:
        raise ValueError('amount_w should be greater than 0')
    if entropy_w < 0:
        raise ValueError('entropy_w should be greater than 0')
    if entropy_n < 0:
        raise ValueError('entropy_n should be greater than 0')
    if amount_n < 0:
        raise ValueError('amount_n should be greater than 0')

    return float(amount_w * entropy_w + amount_n * entropy_n) 

def agc_mixed_004_05(
            self, environment: Environment, template: str,
    ) -> Tuple[str, Optional[str], Callable]:
        """Returns the template source from the environment.

        This considers the loaders on the :attr:`app` and blueprints.
        """
        for loader in self.app.template_loaders:
            if hasattr(loader, "get_source"):
                source, path, uid = loader.get_source(environment, template)
                if source is not None:
                    return source, path, uid

        for loader in self.app.template_loaders:
            if hasattr(loader, "get_source"):
                source, path, uid = loader.get_source(environment, template)
                if source is not None:
                    return source, path, uid

        raise TemplateNotFound(template) 

def agc_mixed_004_06(self, seqprop, structprop, chain_id,
                                      seq_ident_cutoff=0.5, allow_missing_on_termini=0.2,
                                      allow_mutants=True, allow_deletions=False,
                                      allow_insertions=False, allow_unresolved=True):
        """Report if a structure's chain meets the defined cutoffs for sequence quality."""
        seq_ident = seqprop.get_sequence_identity(structprop, chain_id)
        if seq_ident < seq_ident_cutoff:
            return False
        missing_residues = seqprop.get_missing_residues(structprop, chain_id)
        if missing_residues > allow_missing_on_termini:
            return False
        if not allow_mutants and seqprop.has_mutants(structprop, chain_id):
            return False
        if not allow_deletions and seqprop.has_deletions(structprop, chain_id):
            return False
        if not allow_insertions and seqprop.has_insertions(structprop, chain_id):
            return False
        if not allow_unresolved and seqprop.has_unresolved(structprop, chain_id):
            return False
        return True
