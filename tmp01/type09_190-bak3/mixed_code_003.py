def hwc_mixed_003_01(self, curie):
        """ Get a URI from a CURIE """
        if curie is None:
            return None
        parts = curie.split(':')
        if len(parts) == 1:
            if curie != '':
                LOG.error("Not a properly formed curie: \"%s\"", curie)
            return None
        prefix = parts[0]
        if prefix in self.curie_map:
            return '%s%s' % (self.curie_map.get(prefix),
                             curie[(curie.index(':') + 1):])
        LOG.error("Curie prefix not defined for %s", curie)
        return None 

def hwc_mixed_003_02(self):
        """
        Upgrade the serialized object if necessary.

        Raises:
            FutureVersionError: file was written by a future version of the
                software.
        """
        logging.debug("[FeedbackResultsSeries]._upgrade()")
        version = Version.fromstring(self.version)
        logging.debug('[FeedbackResultsSeries] version=%s, class_version=%s',
                      str(version), self.class_version)
        if version > Version.fromstring(self.class_version):
            logging.debug('[FeedbackResultsSeries] version>class_version')
            raise FutureVersionError(Version.fromstring(self.class_version),
                                     version)
        elif version < Version.fromstring(self.class_version):
            if version < Version(0, 1):
                self.time = [None]*len(self.data)
                self.version = str(Version(0, 1)) 

def agc_mixed_003_03(
        self, table_data, primary_key=None, add_primary_key_column=False, index_attrs=None
    ):
        """
        Create a table from :py:class:`tabledata.TableData`.

        :param tabledata.TableData table_data: Table data to create.
        :param str primary_key: |primary_key|
        :param tuple index_attrs: |index_attrs|

        .. seealso::
            :py:meth:`.create_table_from_data_matrix`
        """

        if not isinstance(table_data, TableData):
            raise ValueError("table_data must be an instance of TableData")
        if primary_key and primary_key not in table_data.headers:
            raise ValueError(f"primary_key {primary_key} not found in table_data headers")
        if index_attrs:
            for index_attr in index_attrs:
                if index_attr not in table_data.headers:
                    raise ValueError(f"index_attr {index_attr} not found in table_data headers")
        data_matrix = table_data.to_data_matrix()
        table = self.create_table_from_data_matrix(
            data_matrix, primary_key=primary_key, add_primary_key_column=add_primary_key_column, index_attrs=index_attrs
        )

        return table 

def hwc_mixed_003_04(length=12,
                      allowed_chars='abcdefghijklmnopqrstuvwxyz'
                                    'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
    """
    Return a securely generated random string.
    The default length of 12 with the a-z, A-Z, 0-9 character set returns
    a 71-bit value. log_2((26+26+10)^12) =~ 71 bits
    """
    if not using_sysrandom:
        # This is ugly, and a hack, but it makes things better than
        # the alternative of predictability. This re-seeds the PRNG
        # using a value that is hard for an attacker to predict, every
        # time a random string is required. This may change the
        # properties of the chosen random sequence slightly, but this
        # is better than absolute predictability.
        random.seed(
            hashlib.sha256(
                ('%s%s%s' % (random.getstate(), time.time(), settings.SECRET_KEY)).encode()
            ).digest()
        )
        return ''.join(random.choice(allowed_chars) for i in range(length)) 

def agc_mixed_003_05(self, block_id, addresses):
        """Returns a list of address/data pairs (str, bytes)"""
        if not isinstance(block_id, str):
            raise TypeError("block_id must be a str")
        if not isinstance(addresses, list):
            raise TypeError("addresses must be a list")
        if not all(isinstance(address, str) for address in addresses):
            raise TypeError("addresses must be a list of str")
        if not all(len(address) == 42 for address in addresses):
            raise ValueError("addresses must be a list of 42-char str")
        results = []
        for address in addresses:
            data = self.state_db.get(block_id, address)
            results.append((address, data))

        return results 

def agc_mixed_003_06(self, database, query, properties=None):
        """Executes a management command.
        :param str database: Database against query will be executed.
        :param str query: Query to be executed.
        :param azure.kusto.data.request.ClientRequestProperties properties: Optional additional properties.
        :return: Kusto response data set.
        :rtype: azure.kusto.data._response.KustoResponseDataSet
        """
        if not database:
            raise ValueError("Database cannot be empty")
        if not query:
            raise ValueError("Query cannot be empty")
        if properties and not isinstance(properties, ClientRequestProperties):
            raise ValueError("properties must be of type ClientRequestProperties")
        url = f"{self._cluster_uri}/v1/rest/mgmt"
        data = {
            "db": database,
            "query": query,
        }
        if properties:
            data["properties"] = properties.to_dict()
        response = self._session.post(url, json=data)
        response.raise_for_status()
        return KustoResponseDataSet(response.json())
