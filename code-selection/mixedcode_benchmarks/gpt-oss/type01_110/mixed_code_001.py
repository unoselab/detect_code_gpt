def agc_mixed_001_01(self, typed=True):
        """
        Get the appropriate XML decoder.
        @return: Either the (basic|typed) unmarshaller.
        @rtype: L{UmxTyped}
        """
        if typed:
            if not hasattr(self, "_typed_unmarshaller"):
                self._typed_unmarshaller = self._create_unmarshaller(True)
            return self._typed_unmarshaller
        else:
            if not hasattr(self, "_unmarshaller"):
                self._unmarshaller = self._create_unmarshaller(False)
            return self._unmarshaller 

def hwc_mixed_001_02(self, index, role=Qt.DisplayRole):
        """Cell content"""
        if not index.isValid():
            return None
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return ' '
        if role == Qt.BackgroundColorRole:
            color = self.color_da[index.row(), index.column()].values
            return QtGui.QColor.fromRgbF(*color)
        return None 

def agc_mixed_001_03(self):
        """Update unit description label and field widgets.

        .. note:: This is an automatic Qt slot
           executed when the unit selection changes.
        """
        selected_items = self.lstUnits.selectedItems()
        if not selected_items:
            # No selection: clear description and disable all field widgets
            if hasattr(self, "lblUnitDescription"):
                self.lblUnitDescription.setText("")
            for w in getattr(self, "fieldWidgets", []):
                w.setEnabled 

def agc_mixed_001_04(tag, value):
    """
    Setters for data that also work with implicit transfersyntax

    :param value: the value to set on the tag
    :param tag: the tag to read
    """
    try:
        vr = tag.VR
    except AttributeError:
        raise TypeError("tag must be a pydicom DataElement with a VR attribute")
    # Allow setting FD values even if the element's VR is not FD (e.g., when using implicit VR)
    # but warn if mismatched.
    if vr != "FD":
        import warnings
        warnings.warn(f"Setting FD value on element with VR '{vr}'", UserWarning)
    # Convert the incoming value(s) to float 

def hwc_mixed_001_05(self, serverUrl, username=None):
        """
        returns a handler to access a federated server

        serverUrl - url to the server. Example:
                    https://server.site.com/arcgis
        username - the portal site username. if None is passed, it obtains
         it from the portal properties
        Outout:
          returns a PortalServerSecurityHandler object

        Usage:
        >>> # access the administration site
        >>> serverUrl="https://mysite.site.com/arcgis"
        >>> newSH = sh.portalServerHandler(serverUrl=serverUrl,
                                           username=None)
        >>> agsAdmin = AGSAdministration(url=serverUrl, securityHandler=newSH)
        >>> print agsAdmin.info
        >>> # access a secure service from portal handler
        >>> msUrl = "https://mysite.site.com:6443/arcgis/rest/services/SampleWorldCities/MapServer"
        >>> ms = arcrest.ags.MapService(url=msUrl, securityHandler=newSH)
        >>> print ms.mapName
        """

        pssh = PortalServerSecurityHandler(tokenHandler=self,
                                           serverUrl=serverUrl,
                                           referer=self._referer_url)


        return pssh 

def hwc_mixed_001_06(brain_or_object):
    """Return a ZCatalog brain for the object

    :param brain_or_object: A single catalog brain or content object
    :type brain_or_object: ATContentType/DexterityContentType/CatalogBrain
    :returns: True if the object is a catalog brain
    :rtype: bool
    """
    if is_brain(brain_or_object):
        return brain_or_object
    if is_root(brain_or_object):
        return brain_or_object

    # fetch the brain by UID
    uid = get_uid(brain_or_object)
    uc = get_tool("uid_catalog")
    results = uc({"UID": uid}) or search(query={'UID': uid})
    if len(results) == 0:
        return None
    if len(results) > 1:
        fail(500, "More than one object with UID={} found in portal_catalog".format(uid))
    return results[0]
