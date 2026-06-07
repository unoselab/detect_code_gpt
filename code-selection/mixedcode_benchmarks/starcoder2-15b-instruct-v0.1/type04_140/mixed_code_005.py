def hwc_mixed_005_01(self, **kwargs):
        """Auto Generated Code
        """
        config = ET.Element("config")
        rule = ET.SubElement(config, "rule", xmlns="urn:brocade.com:mgmt:brocade-aaa")
        index_key = ET.SubElement(rule, "index")
        index_key.text = kwargs.pop('index')
        command = ET.SubElement(rule, "command")
        cmdlist = ET.SubElement(command, "cmdlist")
        interface_m = ET.SubElement(cmdlist, "interface-m")
        interface_management_leaf = ET.SubElement(interface_m, "interface-management-leaf")
        interface = ET.SubElement(interface_management_leaf, "interface")
        management_leaf = ET.SubElement(interface, "management-leaf")
        management_leaf.text = kwargs.pop('management_leaf')

        callback = kwargs.pop('callback', self._callback)
        return callback(config) 

def agc_mixed_005_02(
        self,
        description,
        event_id="0.0.0",
        rules_id="0.0.0",
        asset=None,
        delay_before_settling=0,
        never_in_play=False,
        resolution_constraint="exactly_one_winner",
        account=None,
        **kwargs
    ):
        """ Create an betting market. This needs to be **proposed**.

            :param list description: Internationalized list of descriptions
            :param str event_id: Event ID to create this for (defaults to
                *relative* id ``0.0.0``)
            :param str rule_id: Rule ID to create this with (defaults to
                *relative* id ``0.0.0``)
            :param peerplays.asset.Asset asset: Asset to be used for this
                market
            :param int delay_before_settling: Delay in seconds before settling
                (defaults to 0 seconds - immediatelly)
            :param bool never_in_play: Set this market group as *never in play*
                (defaults to *False*)
            :param str account: (optional) the account to allow access
                to (defaults to ``default_account``)
        """
        return self.propose(
            "betting_market_group_create",
            description=description,
            event_id=event_id,
            rules_id=rules_id,
            asset=asset,
            delay_before_settling=delay_before_settling,
            never_in_play=never_in_play,
            resolution_constraint=resolution_constraint,
            account=account,
            **kwargs
        ) 

def hwc_mixed_005_03(self, path, fh=None):
    """Reads a directory given by path.

    Args:
      path: The path to list children of.
      fh: A file handler. Not used.

    Yields:
      A generator of filenames.

    Raises:
      FuseOSError: If we try and list a file.

    """
    del fh

    # We can't read a path if it's a file.
    if not self._IsDir(path):
      raise fuse.FuseOSError(errno.ENOTDIR)

    fd = aff4.FACTORY.Open(self.root.Add(path), token=self.token)

    children = fd.ListChildren()

    # Make these special directories unicode to be consistent with the rest of
    # aff4.
    for directory in [u".", u".."]:
      yield directory

    # ListChildren returns a generator, so we do the same.
    for child in children:
      # Filter out any directories we've chosen to ignore.
      if child.Path() not in self.ignored_dirs:
        yield child.Basename() 

def agc_mixed_005_04(dataset_label=None, destination_dir=None, dry_run=False):
    """Download sample data by data label. Warning: function with side effect!

    Labels can be listed by sample_data.data_urls.keys(). Returns downloaded files.

    :param dataset_label: label of data. If it is set to None, all data are downloaded
    :param destination_dir: output dir for data
    :param dry_run: runs function without downloading anything
    """
    if destination_dir is None:
        destination_dir = os.getcwd()
    if dry_run:
        print("Dry run: No data will be downloaded.")
        return []
    if dataset_label is None:
        data_labels = sample_data.data_urls.keys()
    else:
        data_labels = [dataset_label]
    downloaded_files = []
    for label in data_labels:
        url = sample_data.data_urls[label]
        filename = os.path.join(destination_dir, os.path.basename(url))
        urllib.request.urlretrieve(url, filename)
        downloaded_files.append(filename)

    return downloaded_files 

def hwc_mixed_005_05(self, data):
        """ Parses a V2 data packet at the start of the given data.

        The format of a packet is as follows:

        field_type(varint) payload_len(varint) data[payload_len bytes]

        apart from EOS which has no payload_en or data (it's a single zero
        byte).

        :param data:
        :return: rest of data, PacketV2
        """
        from pymacaroons.exceptions import MacaroonDeserializationException

        ft, n = _decode_uvarint(data)
        data = data[n:]
        if ft == self._EOS:
            return data, PacketV2(ft, None)
        payload_len, n = _decode_uvarint(data)
        data = data[n:]
        if payload_len > len(data):
            raise MacaroonDeserializationException(
                'field data extends past end of buffer')
        return data[payload_len:], PacketV2(ft, data[0:payload_len]) 

def agc_mixed_005_06(self, canvas, stem_color, leaf_color, thickness, ages=None):
        """Draw the tree on a canvas.

        Args:
            canvas (object): The canvas, you want to draw the tree on. Supported canvases: svgwrite.Drawing and PIL.Image (You can also add your custom libraries.)
            stem_color (tupel): Color or gradient for the stem of the tree.
            leaf_color (tupel): Color for the leaf (= the color for last iteration).
            thickness (int): The start thickness of the tree.
        """
        if ages is None:
            ages = [self.age] * self.height
        if len(ages)!= self.height:
            raise ValueError("The length of ages must be equal to the height of the tree.")
        if isinstance(canvas, svgwrite.Drawing):
            self._draw_on_svg(canvas, stem_color, leaf_color, thickness, ages)
        elif isinstance(canvas, PIL.Image):
            self._draw_on_pil(canvas, stem_color, leaf_color, thickness, ages)
        else:
            raise ValueError("Unsupported canvas type.")
