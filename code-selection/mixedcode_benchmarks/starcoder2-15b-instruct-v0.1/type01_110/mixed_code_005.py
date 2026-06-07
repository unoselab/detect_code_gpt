def hwc_mixed_005_01(self, column):
        """
        Adjusts the height for this item based on the columna and its text.

        :param      column | <int>
        """
        tree = self.treeWidget()
        if not tree:
            return

        w = tree.width()
        if tree.verticalScrollBar().isVisible():
            w -= tree.verticalScrollBar().width()

        doc = QtGui.QTextDocument()
        doc.setTextWidth(w)
        doc.setHtml(self.text(0))
        height = doc.documentLayout().documentSize().height()
        self.setFixedHeight(height+2) 

def agc_mixed_005_02(self, region, bbox=None, xy=None):
        """
        Restore the saved region. If bbox (instance of BboxBase, or
        its extents) is given, only the region specified by the bbox
        will be restored. *xy* (a tuple of two floasts) optionally
        specifies the new position (the LLC of the original region,
        not the LLC of the bbox) where the region will be restored.

        >>> region = renderer.copy_from_bbox()
        >>> x1, y1, x2, y2 = region.get_extents()
        >>> renderer.restore_region(region, bbox=(x1+dx, y1, x2, y2),
        ...                         xy=(x1-dx, y1))

        """
        if bbox is not None:
            x1, y1, x2, y2 = bbox.get_extents()
            region = region.crop((x1, y1, x2, y2))
        if xy is not None:
            x, y = xy
            region = region.offset(x - x1, y - y1)
        self.restore_region(region) 

def hwc_mixed_005_03(self, delay):
        """Setter method; for a description see the getter method."""
        if isinstance(delay, (int, float)) and delay >= 0 or delay is None:
            self._response_delay = delay
        else:
            raise ValueError(
                _format("Invalid value for response_delay: {0!A}, must be a "
                        "positive number", delay)) 

def hwc_mixed_005_04(self):
        """
        Returns the VM state (e.g. running, paused etc.)

        :returns: state (string)
        """

        result = yield from self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name == "VMState":
                    return value.strip('"')
        return "unknown" 

def agc_mixed_005_05(self, full_properties=False, filter_args=None):
        """
        List the Ports of this Adapter.

        If the adapter does not have any ports, an empty list is returned.

        Authorization requirements:

        * Object-access permission to this Adapter.

        Parameters:

          full_properties (bool):
            Controls whether the full set of resource properties should be
            retrieved, vs. only the short set as returned by the list
            operation.

          filter_args (dict):
            Filter arguments that narrow the list of returned resources to
            those that match the specified filter arguments. For details, see
            :ref:`Filtering`.

            `None` causes no filtering to happen, i.e. all resources are
            returned.

        Returns:

          : A list of :class:`~zhmcclient.Port` objects.

        Raises:

          :exc:`~zhmcclient.HTTPError`
          :exc:`~zhmcclient.ParseError`
          :exc:`~zhmcclient.AuthError`
          :exc:`~zhmcclient.ConnectionError`
        """
        port_resources = self.manager.list_resources(
            resource_type='port',
            parent_type='adapter',
            parent_uri=self.uri,
            full_properties=full_properties,
            filter_args=filter_args)
        return [Port(manager=self.manager, resource=port_resource)
                for port_resource in port_resources] 

def agc_mixed_005_06(self, line):
        """allowaccess <subject> [access-level] Set the access level for subject Access
        level is "read", "write" or "changePermission".

        Access level defaults to "read" if not specified. Special subjects:   public:
        Any subject, authenticated and not authenticated   authenticatedUser: Any
        subject that has authenticated with CILogon   verifiedUser: Any subject that has
        authenticated with CILogon and has been verified by DataONE

        """
        args = line.split()
        if len(args) not in [2, 3]:
            raise Exception("Invalid number of arguments")
        subject = args[0]
        access_level = args[1] if len(args) == 3 else "read"
        if access_level not in ["read", "write", "changePermission"]:
            raise Exception("Invalid access level")
        self.acl.allow_access(subject, access_level)
