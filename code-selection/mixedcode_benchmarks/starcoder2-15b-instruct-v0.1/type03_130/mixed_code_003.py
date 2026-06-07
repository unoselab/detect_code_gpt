def hwc_mixed_003_01(self, init):
        """
        return the non-direct init if the direct algorithm has been selected.
        """
        crc = init
        for i in range(self.Width):
            bit = crc & 0x01
            if bit:
                crc^= self.Poly
            crc >>= 1
            if bit:
                crc |= self.MSB_Mask
        return crc & self.Mask 

def agc_mixed_003_02(self, *nodes: Union[AbstractNode, str]) -> None:
        """Replace this node with nodes.

        If nodes contains ``str``, it will be converted to Text node.
        """
        parent = self.parent
        if parent is None:
            raise ValueError("Cannot replace the root node.")
        index = parent.children.index(self)
        parent.children = parent.children[:index] + list(nodes) + parent.children[index + 1:]
        for node in nodes:
            if isinstance(node, str):
                node = TextNode(node)
            node.parent = parent 

def hwc_mixed_003_03(self, sgraph):
        """Adds an subgraph object to the graph.

        It takes a subgraph object as its only argument and returns
        None.
        """

        if not isinstance(sgraph, Subgraph) and not isinstance(sgraph, Cluster):
            raise TypeError('add_subgraph() received a non subgraph class object:' + str(sgraph))

        if self.obj_dict['subgraphs'].has_key(sgraph.get_name()):

            sgraph_list = self.obj_dict['subgraphs'][ sgraph.get_name() ]
            sgraph_list.append( sgraph.obj_dict )

        else:
            self.obj_dict['subgraphs'][ sgraph.get_name() ] = [ sgraph.obj_dict ]

        sgraph.set_sequence( self.get_next_sequence_number() )

        sgraph.set_parent_graph( self.get_parent_graph() ) 

def agc_mixed_003_04(self, key, value=1):
        """Set the specified key/value in the per-message measurements

        .. versionadded:: 3.13.0

        .. note:: If this method is called when there is not a message being
            processed, a message will be logged at the ``warning`` level to
            indicate the value is being dropped. To suppress these warnings,
            set the :attr:`rejected.consumer.Consumer.IGNORE_OOB_STATS`
            attribute to :data:`True`.

        :param key: The key to set the value for
        :type key: :class:`str`
        :param value: The value
        :type value: :class:`int` or :class:`float`

        """
        if not self._message:
            if not self.IGNORE_OOB_STATS:
                self.logger.warning(
                    "stats_set_value called outside of a message processing "
                    "context; value will be dropped"
                )
            return
        self._message.stats.set_value(key, value) 

def hwc_mixed_003_05(self, path):
        """
        this borrows too much from the internals of ofs
        maybe expose different parts of the api?
        """
        from datetime import datetime
        from StringIO import StringIO
        path = path.lstrip("/")
        bucket, label = path.split("/", 1)

        bucket = self.ofs._require_bucket(bucket)
        key = self.ofs._get_key(bucket, label)
        if key is None:
            key = bucket.new_key(label)
            self.ofs._update_key_metadata(key, { '_creation_time': str(datetime.utcnow()) })
            key.set_contents_from_file(StringIO(''))
        key.close() 

def agc_mixed_003_06(table, field=-1):
    """Use the Django ORM or collections.Counter to count unique values of a field in a table

    `table` is one of:
    1. An iterable of Django model instances for a database table (e.g. a Django queryset)
    2. An iterable of dicts or lists with elements accessed by row[field] where field can be an integer or string
    3. An iterable of objects or namedtuples with elements accessed by `row.field`

    `field` can be any immutable object (the key or index in a row of the table that access the value to be counted)
    """
    if isinstance(table, QuerySet):
        values = table.values_list(field, flat=True)
    elif isinstance(table, (list, tuple)):
        if isinstance(table[0], dict):
            values = [row[field] for row in table]
        elif isinstance(table[0], (list, tuple)):
            values = [row[field] for row in table]
        else:
            values = [getattr(row, field) for row in table]
    else:
        raise ValueError("Invalid table type")
    return Counter(values)
