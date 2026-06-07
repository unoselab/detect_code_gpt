def hwc_mixed_002_01(self, **kwargs):
        """Auto Generated Code
        """
        config = ET.Element("config")
        nacm = ET.SubElement(config, "nacm", xmlns="urn:ietf:params:xml:ns:yang:ietf-netconf-acm")
        rule_list = ET.SubElement(nacm, "rule-list")
        name_key = ET.SubElement(rule_list, "name")
        name_key.text = kwargs.pop('name')
        rule = ET.SubElement(rule_list, "rule")
        name_key = ET.SubElement(rule, "name")
        name_key.text = kwargs.pop('name')
        action = ET.SubElement(rule, "action")
        action.text = kwargs.pop('action')

        callback = kwargs.pop('callback', self._callback)
        return callback(config) 

def agc_mixed_002_02(self, tx, tx_in_idx, generator):
        """
        For a given script, iterate over and pull out public pairs encoded as sec values.
        """
        for i in range(len(tx.outputs)):
            if i == tx_in_idx:
                continue
            script = tx.outputs[i].script
            if script is None:
                continue
            for pair in self.public_pairs_for_script(script, generator):
                yield pair 

def agc_mixed_002_03(self, section, option, value=''):
        """
        This function is unique to the GitConfigParser. It will add another
        value for the option if it already exists, converting the option's
        value to a list if applicable.

        If "value" is a list, then any existing values for the specified
        section and option will be replaced with the list being passed.
        """
        if not self.has_section(section):
            self.add_section(section)
        if not self.has_option(section, option):
            self.set(section, option, value)
        else:
            if isinstance(value, list):
                self.set(section, option, value)
            else:
                self.set(section, option, self.get(section, option) + ' ' + value) 

def agc_mixed_002_04(self, table_type):
        """Read either the hash or block table of a MPQ archive."""

        if table_type == 'hash':
            table = self.hash_table
        elif table_type == 'block':
            table = self.block_table
        else:
            raise ValueError('Unknown table type')

        # Read the table
        table.clear()
        table.extend(self.read_table_entry(table_type) for _ in range(self.header.num_tables[table_type]))

        # Sort the table
        table.sort(key=lambda entry: entry.block_pos) 

def hwc_mixed_002_05(id_list: Iterable[str]) -> Dict[str, List[str]]:
    """
    Given a list of ids return their types

    :param id_list: list of ids
    :return: dictionary where the id is the key and the value is a list of types
    """
    type_map = {}
    filter_out_types = [
        'cliqueLeader',
        'Class',
        'Node',
        'Individual',
        'quality',
        'sequence feature'
    ]

    for node in get_scigraph_nodes(id_list):
        type_map[node['id']] = [typ.lower() for typ in node['meta']['types']
                                if typ not in filter_out_types]

    return type_map 

def hwc_mixed_002_06(cls, data):
        """Transforms a Python dictionary to an Output object.

            Note:
                To pass a serialization cycle multiple times, a
                Cryptoconditions Fulfillment needs to be present in the
                passed-in dictionary, as Condition URIs are not serializable
                anymore.

            Args:
                data (dict): The dict to be transformed.

            Returns:
                :class:`~bigchaindb.common.transaction.Output`
        """
        try:
            fulfillment = _fulfillment_from_details(data['condition']['details'])
        except KeyError:
            # NOTE: Hashlock condition case
            fulfillment = data['condition']['uri']
        try:
            amount = int(data['amount'])
        except ValueError:
            raise AmountError('Invalid amount: %s' % data['amount'])
        return cls(fulfillment, data['public_keys'], amount)
