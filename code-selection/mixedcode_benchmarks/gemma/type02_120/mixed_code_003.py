def hwc_mixed_003_01(self, line):
        """Try parsing compound attribute string.

        Return a dictionary with single attributes in 'line'.
        """

        attrs = line.split(';')
        attrs = [a.strip() for a in attrs]
        attrs = filter(lambda a:len(a)>0, attrs)

        new_attrs = {}
        for a in attrs:
            k, v = a.split(':')
            k, v = [s.strip() for s in (k, v)]
            new_attrs[k] = v

        return new_attrs 

def hwc_mixed_003_02(pode, leaf=False):
    """
    Get all the tags for a given node.

    Args:
        pode (tuple): A packed node.
        leaf (bool): If True, only return the full tags.

    Returns:
        list: A list of tag strings.
    """
    fulltags = [tag for tag in pode[1]['tags']]
    if not leaf:
        return fulltags

    # longest first
    retn = []

    # brute force rather than build a tree.  faster in small sets.
    for size, tag in sorted([(len(t), t) for t in fulltags], reverse=True):
        look = tag + '.'
        if any([r.startswith(look) for r in retn]):
            continue
        retn.append(tag)
    return retn 

def hwc_mixed_003_03(self):
        """
        Set up screen properties
        """
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_MAGENTA, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_GREEN, -1)
        curses.init_pair(6, curses.COLOR_BLUE, -1)
        curses.init_pair(7, curses.COLOR_RED, -1) 

def agc_mixed_003_04(self, router_ids=None):

        """Fetch router data from the routing plugin in chunks.

                :param router_ids: List of router_ids of routers to fetch
                :return: List of router dicts of format:
                         [ {router_dict1}, {router_dict2},.....]
        """

        if router_ids is None:
            return []

        chunk_size = 100
        all_routers = []
        for i in range(0, len(router_ids), chunk_size):
            chunk = router_ids[i : i + chunk_size]
            routers = self.routing_plugin.get_routers(router_ids=chunk)
            all_routers.extend(routers)

        return all_routers 

def agc_mixed_003_05(
        state: MediatorTransferState,
        channelidentifiers_to_channels: ChannelMap,
        secret: Secret,
        secrethash: SecretHash,
        block_number: BlockNumber,
) -> List[Event]:
    """ Set the secret to all mediated transfers.

    The secret should have been learned from the secret registry.
    """
    if channel_id in state.mediated_transfers:
        transfer = state.mediated_transfers[channel_id]
        if transfer.secrethash == secrethash:
            transfer.secret = secret
            events.append(MediatedTransferSecretSet(
                channel_id=channel_id,
                secret=secret,
                block_number=block_number
            ))
return events 

def agc_mixed_003_06(self, subcmd, opts):
        """${cmd_name}: make a filterfile and spit it to stdout.
        """
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
            tmp.write(opts.get('content', ''))
            tmp_path = tmp.name

        try:
            with open(tmp_path, 'r') as f:
                print(f.read(), end='')
        finally:
            os.remove(tmp_path)
