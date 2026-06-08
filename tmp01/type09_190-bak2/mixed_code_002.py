def agc_mixed_002_01(self, subnetId, domainId):
        """ Function removeDomain
        Delete a domain from a subnet

        @param subnetId: The subnet Id
        @param domainId: The domainId to be attached wiuth the subnet
        @return RETURN: boolean
        """
        try:
            subnet = self.getSubnet(subnetId)
            if subnet is None:
                return False

            if domainId in subnet.domains:
                subnet.domains.remove(domainId)
                subnet.save()
                return True
            else:
                return False
        except Exception as e:
            log.error("Exception: %s" % str(e))
            return False 

def agc_mixed_002_02(self, key):
        """
        Returns a list with keys of this DAWG that are prefixes of the ``key``.
        """
        prefixes = []
        node = self.root
        for char in key:
            if char not in node.children:
                return []
            node = node.children[char]
        queue = [(node, key)]
        while queue:
            node, prefix = queue.pop(0)
            if node.is_word:
                prefixes.append(prefix)
            for char, child in node.children.items():
                queue.append((child, prefix + char))

        return prefixes 

def hwc_mixed_002_03( self, path_info, blockchain_name, blockheight ):
        """
        Get the name's historic name operations
        Reply the list of nameops at the given block height
        Reply 404 for blockchains other than those supported
        Reply 502 for any error we have in talking to the blockstack server
        """
        try:
            blockheight = int(blockheight)
            assert check_block(blockheight)
        except:
            return self._reply_json({'error': 'Invalid block'}, status_code=400)

        if blockchain_name != 'bitcoin':
            # not supported
            return self._reply_json({'error': 'Unsupported blockchain'}, status_code=404)

        blockstackd_url = get_blockstackd_url()
        nameops = blockstackd_client.get_blockstack_transactions_at(int(blockheight), hostport=blockstackd_url)
        if json_is_error(nameops):
            # error
            status_code = nameops.get('http_status', 502)
            return self._reply_json({'error': nameops['error']}, status_code=status_code)

        self._reply_json(nameops)
        return 

def agc_mixed_002_04(tax_benefit_system, nb_persons, nb_groups):
    """
        Generate a dictionnary of dataframes containing nb_persons persons spread in nb_groups groups.

        :param TaxBenefitSystem tax_benefit_system: the tax_benefit_system to use
        :param int nb_persons: the number of persons in the system
        :param int nb_groups: the number of collective entities in the system

        :returns: A dictionary whose keys are entities and values the corresponding data frames

        Example:

        >>> from openfisca_survey_manager.input_dataframe_generator import make_input_dataframe_by_entity
        >>> from openfisca_country_template import CountryTaxBenefitSystem
        >>> tbs = CountryTaxBenefitSystem()
        >>> input_dataframe_by_entity = make_input_dataframe_by_entity(tbs, 400, 100)
        >>> sorted(input_dataframe_by_entity['person'].columns.tolist())
        ['household_id', 'household_legacy_role', 'household_role', 'person_id']
        >>> sorted(input_dataframe_by_entity['household'].columns.tolist())
        []
    """
    input_dataframe_by_entity = {}
    for entity in tax_benefit_system.entities:
        input_dataframe_by_entity[entity] = pd.DataFrame(columns=tax_benefit_system.get_attributes_of(entity))
    persons_per_group = nb_persons // nb_groups
    for i in range(nb_groups):
        group_persons = input_dataframe_by_entity['person'].copy()
        for j in range(persons_per_group):
            person_id = f'person_{i}_{j}'
            group_persons = group_persons.append({
                'person_id': person_id,
                'household_id': f'household_{i}',
                'household_role':'member',
                'household_legacy_role':'member'
            }, ignore_index=True)
        input_dataframe_by_entity['person'] = input_dataframe_by_entity['person'].append(group_persons, ignore_index=True)
    return input_dataframe_by_entity 

def hwc_mixed_002_05(cdata, sym):
    """ Ensures that the data within cdata has double sphere symmetry.

    Example::

        >>> spherepy.doublesphere(cdata, 1)

    Args:
        sym (int): is 1 for scalar data and -1 for vector data

    Returns:
        numpy.array([*,*], dtype=np.complex128) containing array with 
        doublesphere symmetry.
    """

    nrows = cdata.shape[0]
    ncols = cdata.shape[1]

    ddata = np.zeros([nrows, ncols], dtype=np.complex128)

    for n in xrange(0, nrows):
        for m in xrange(0, ncols):
            s = sym * cdata[np.mod(nrows - n, nrows),
                          np.mod(int(np.floor(ncols / 2)) + m, ncols)]
            t = cdata[n, m]

            if s * t == 0:
                ddata[n, m] = s + t
            else:
                ddata[n, m] = (s + t) / 2

    return ddata 

def hwc_mixed_002_06(self, callback=False):
        """Send an unsubscribe for all active subscriptions"""
        futures = ((f, r) for f, r in self._requests.items()
                   if isinstance(r, Subscribe)
                   and f not in self._pending_unsubscribes)
        if futures:
            for future, request in futures:
                if callback:
                    log.warn("Unsubscribing from %s", request.path)
                    cothread.Callback(self.unsubscribe, future)
                else:
                    self.unsubscribe(future)
