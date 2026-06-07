def hwc_mixed_002_01(node_id, purge_data,**kwargs):
    """
        Remove node from DB completely
        If there are attributes on the node, use purge_data to try to
        delete the data. If no other resources link to this data, it
        will be deleted.

    """
    user_id = kwargs.get('user_id')
    try:
        node_i = db.DBSession.query(Node).filter(Node.id == node_id).one()
    except NoResultFound:
        raise ResourceNotFoundError("Node %s not found"%(node_id))

    group_items = db.DBSession.query(ResourceGroupItem).filter(
                                        ResourceGroupItem.node_id==node_id).all()
    for gi in group_items:
        db.DBSession.delete(gi)

    if purge_data == 'Y':
        _purge_datasets_unique_to_resource('NODE', node_id)

    log.info("Deleting node %s, id=%s", node_i.name, node_id)

    node_i.network.check_write_permission(user_id)
    db.DBSession.delete(node_i)
    db.DBSession.flush()
    return 'OK' 

def agc_mixed_002_02(self, name, ns=None, default=None):
        """
        Get an attribute by name and (optional) namespace
        @param name: The name of a contained attribute (may contain prefix).
        @type name: basestring
        @param ns: An optional namespace
        @type ns: (I{prefix}, I{name})
        @param default: Returned when attribute not-found.
        @type default: L{Attribute}
        @return: The requested attribute object.
        @rtype: L{Attribute}
        """
        if ns is None:
            ns = self.namespace
        if ns is None:
            return default
        prefix, name = ns
        if prefix is None:
            prefix = self.namespace.prefix
        if prefix is None:
            return default
        if prefix not in self.attributes:
            return default
        return self.attributes[prefix][name] 

async def agc_mixed_002_03(self):
        """Clean up all finished payloads"""
        while True:
            await asyncio.sleep(1)
            for payload in list(self._payloads.values()):
                if payload.done:
                    self._payloads.pop(payload.id)
                    self.logger.debug(
                        "Payload %s finished", payload.id, extra={"payload": payload}
                    ) 

def agc_mixed_002_04(self, **extra_kwargs):
        """
        Create page (and page title) in default language

        extra_kwargs will be pass to cms.api.create_page()
        e.g.:
            extra_kwargs={
                "soft_root": True,
                "reverse_id": my_reverse_id,
            }
        """
        page = cms.api.create_page(
            title=self.title,
            language=settings.LANGUAGES[0][0],
            template=self.template,
            **extra_kwargs
        )

        # Create page title in default language
        cms.api.add_title(
            page=page,
            language=settings.LANGUAGES[0][0],
            title=self.title,
        )

        return page 

def hwc_mixed_002_05(func, args_iter, **kwargs):
    """
    enqueues a function with iterable arguments
    """
    iter_count = len(args_iter)
    iter_group = uuid()[1]
    # clean up the kwargs
    options = kwargs.get('q_options', kwargs)
    options.pop('hook', None)
    options['broker'] = options.get('broker', get_broker())
    options['group'] = iter_group
    options['iter_count'] = iter_count
    if options.get('cached', None):
        options['iter_cached'] = options['cached']
    options['cached'] = True
    # save the original arguments
    broker = options['broker']
    broker.cache.set('{}:{}:args'.format(broker.list_key, iter_group), SignedPackage.dumps(args_iter))
    for args in args_iter:
        if not isinstance(args, tuple):
            args = (args,)
        async_task(func, *args, **options)
    return iter_group 

def hwc_mixed_002_06(self, entrez):
        """Convert Entrez Id to Uniprot Id"""
        server = "http://www.uniprot.org/uniprot/?query=%22GENEID+{0}%22&format=xml".format(entrez)
        r = requests.get(server, headers={"Content-Type": "text/xml"})
        if not r.ok:
            r.raise_for_status()
            sys.exit()
        response = r.text
        info = xmltodict.parse(response)
        try:
            data = info['uniprot']['entry']['accession'][0]
            return data
        except TypeError:
            data = info['uniprot']['entry'][0]['accession'][0]
            return data
