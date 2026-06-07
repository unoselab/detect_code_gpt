def hwc_mixed_002_01(self, polynomial):
        """Precomputes a CRC-64 lookup table seeded from the supplied polynomial.
           No return value.
        """

        self._lookup_table = []

        for i in range(0, 256):
            lookup_value = i

            for _ in range(0, 8):
                if lookup_value & 0x1 == 0x1:
                    lookup_value = (lookup_value >> 1) ^ polynomial

                else:
                    lookup_value = lookup_value >> 1

            self._lookup_table.append(lookup_value) 

def agc_mixed_002_02(self, s, level=0, color=None):
        """Write message with indentation, context and optional timestamp."""
        if self.enabled:
            if self.timestamp:
                s = "%s %s" % (datetime.datetime.now().strftime("%H:%M:%S.%f"), s)
            if self.context:
                s = "%s %s" % (self.context, s)
            if self.indent:
                s = "%s%s" % (self.indent * level, s)
            if color:
                s = color(s)
            print(s) 

def hwc_mixed_002_03(host):
    """ Put your host information in the prefix object. """
    p = new_prefix()
    p.prefix = str(host['ipaddr'])
    p.type = "host"
    p.description = host['description']
    p.node = host['fqdn']
    p.avps = {}

    # Use remaining data from ipplan to populate comment field.
    if 'additional' in host:
        p.comment = host['additional']

    # Use specific info to create extra attributes.
    if len(host['location']) > 0:
        p.avps['location'] = host['location']

    if len(host['mac']) > 0:
        p.avps['mac'] = host['mac']

    if len(host['phone']) > 0:
        p.avps['phone'] = host['phone']

    if len(host['user']) > 0:
        p.avps['user'] = host['user']

    return p 

def agc_mixed_002_04(self):
        """
        Indicated most recent update of the instance, assumption based on:
        - if currentWorkflow exists, its startedAt time is most recent update.
        - else max of workflowHistory startedAt is most recent update.
        """
        if self.currentWorkflow:
            return self.currentWorkflow.startedAt
        else:
            return max(
                [
                    workflow.startedAt
                    for workflow in self.workflowHistory
                    if workflow.startedAt
                ]
            ) 

def agc_mixed_002_05(
    nlp,
    conllu_file,
    text_file,
    raw_text=True,
    oracle_segments=False,
    max_doc_length=None,
    limit=None,
):
    """Read the CONLLU format into (Doc, GoldParse) tuples. If raw_text=True,
    include Doc objects created using nlp.make_doc and then aligned against
    the gold-standard sequences. If oracle_segments=True, include Doc objects
    created from the gold-standard segments. At least one must be True."""
    if not (raw_text or oracle_segments):
        raise ValueError("At least one of raw_text or oracle_segments must be True")
    if raw_text and oracle_segments:
        raise ValueError("Only one of raw_text or oracle_segments may be True")
    if raw_text:
        docs = read_docs(nlp, text_file, max_doc_length=max_doc_length, limit=limit)
    else:
        docs = []
    gold_parses = read_gold_parses(conllu_file, limit=limit)
    for gold_parse in gold_parses:
        if raw_text:
            doc = docs[gold_parse.doc_id]
        else:
            doc = nlp.make_doc(gold_parse.text)
        yield doc, gold_parse 

def hwc_mixed_002_06(query_type, session=None, order=None, **bfilter):
    """Look up 'query_type' Nexus VPC Allocs matching the filter.

    :param query_type: 'all', 'one' or 'first'
    :param session: db session
    :param order: select what field to order data
    :param bfilter: filter for mappings query
    :returns: VPCs if query gave a result, else
             raise NexusVPCAllocNotFound.
    """

    if session is None:
        session = bc.get_reader_session()

    if order:
        query_method = getattr(session.query(
            nexus_models_v2.NexusVPCAlloc).filter_by(**bfilter).order_by(
                order),
            query_type)
    else:
        query_method = getattr(session.query(
            nexus_models_v2.NexusVPCAlloc).filter_by(**bfilter), query_type)

    try:
        vpcs = query_method()
        if vpcs:
            return vpcs
    except sa_exc.NoResultFound:
        pass

    raise c_exc.NexusVPCAllocNotFound(**bfilter)
