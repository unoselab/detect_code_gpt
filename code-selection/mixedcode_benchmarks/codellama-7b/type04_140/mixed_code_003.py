def agc_mixed_003_01(inserted_indices_list, prune_indices_list):
        """Adjust inserted indices, if there are pruned elements."""
        # Created a copy, to preserve cached property
        if not prune_indices_list:
            return inserted_indices_list
        for i, inserted_indices in enumerate(inserted_indices_list):
            prune_indices = prune_indices_list[i]
            if not inserted_indices:
                continue
            if prune_indices:
                inserted_indices = inserted_indices - prune_indices
            inserted_indices_list[i] = inserted_indices
        return inserted_indices_list 

def hwc_mixed_003_02(self, xmpp_message: BeautifulSoup):
        """
        a XMPP 'message' in the case of Kik is the actual stanza we receive when someone sends us a message
        (weather groupchat or not), starts typing, stops typing, reads our message, etc.
        Examples: http://slixmpp.readthedocs.io/api/stanza/message.html
        :param xmpp_message: The XMPP 'message' element we received
        """
        if 'xmlns' in xmpp_message.attrs:
            self._handle_xmlns(xmpp_message['xmlns'], xmpp_message)
        elif xmpp_message['type'] == 'receipt':
            if xmpp_message.g:
                self.callback.on_group_receipts_received(chatting.IncomingGroupReceiptsEvent(xmpp_message))
            else:
                self.xml_namespace_handlers['jabber:client'].handle(xmpp_message)
        else:
            # iPads send messages without xmlns, try to handle it as jabber:client
            self.xml_namespace_handlers['jabber:client'].handle(xmpp_message) 

def hwc_mixed_003_03(self, key, val, priority=None):
        """add a value to the queue with priority, using the key to know uniqueness

        key -- str -- this is used to determine if val already exists in the queue,
            if key is already in the queue, then the val will be replaced in the
            queue with the new priority
        val -- mixed -- the value to add to the queue
        priority -- int -- the priority of val
        """

        if key in self.item_finder:
            self.remove(key)

        else:
            # keep the queue contained
            if self.full():
                raise OverflowError("Queue is full")

        if priority is None:
            priority = next(self.counter)

        item = [priority, key, val]
        self.item_finder[key] = item
        heapq.heappush(self.pq, item) 

def agc_mixed_003_04(flavor_id, project_id, profile=None, **kwargs):
    """
    Add a project to the flavor access list

    CLI Example:

    .. code-block:: bash

        salt '*' nova.flavor_access_add flavor_id=fID project_id=pID
    """
    if profile:
        if "admin" in profile:
            profile = __salt__["config.get"]("nova:admin_profile")
        elif "admin" not in profile:
            profile = __salt__["config.get"]("nova:profile")
    conn = _auth(profile)
    try:
        conn.flavors.add_tenant_access(flavor_id, project_id)
        return True
    except Exception as e:
        log.error(
            "Failed to add project to flavor access list. Exception: %s", e
        )
        return False 

def agc_mixed_003_05(self, spec, recursive = False):
        """ Do the underlying database operations to delete a prefix
        """
        if not recursive:
            if self.get_children(spec):
                return

        # If we are recursive, then we delete all the children
        # of the prefix.
        if recursive:
            for child in self.get_children(spec):
                self._db_remove_prefix(child, recursive)

        # Remove the prefix from the database
        self._db_delete_prefix(spec) 

def hwc_mixed_003_06(self, infile, configspec):
        """this overrides the original ConfigObj method of the same name.  It
        runs through the input file collecting lines into a list.  When
        completed, this method submits the list of lines to the super class'
        function of the same name.  ConfigObj proceeds, completely unaware
        that it's input file has been preprocessed."""
        if isinstance(infile, (six.binary_type, six.text_type)):
            infile = to_str(infile)
            original_path = os.path.dirname(infile)
            expanded_file_contents = self._expand_files(infile, original_path)
            super(ConfigObjWithIncludes, self)._load(
                expanded_file_contents,
                configspec
            )
        else:
            super(ConfigObjWithIncludes, self)._load(infile, configspec)
