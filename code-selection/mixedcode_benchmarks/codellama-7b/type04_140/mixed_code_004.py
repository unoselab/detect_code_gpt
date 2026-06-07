def hwc_mixed_004_01(dstpath, srcpath, names=None, 
                                       languages=None):
    """ Update or add manifest XML from srcpath as resource in dstpath """
    logger.info("Updating manifest from %s in %s", srcpath, dstpath)
    if dstpath.lower().endswith(".exe"):
        name = 1 
    else:
        name = 2
    winresource.UpdateResourcesFromDataFile(dstpath, srcpath, RT_MANIFEST, 
                                         names or [name], 
                                         languages or [0, "*"]) 

def agc_mixed_004_02(self):
        """ Method which loads data from the file
        """
        # pylint: disable=too-many-return-statements
        with open(self.file_name, 'r') as file:
            for line in file:
                if line.startswith('*'):
                    continue
                line = line.strip()
                if line == '':
                    continue
                self.data.append(line) 

def hwc_mixed_004_03(fun):
    """
    Return a dict of the last function called for all minions
    """
    serv = _get_serv(ret=None)
    ret = {}
    for minion in serv.smembers('minions'):
        ind_str = '{0}:{1}'.format(minion, fun)
        try:
            jid = serv.get(ind_str)
        except Exception:
            continue
        if not jid:
            continue
        data = serv.get('{0}:{1}'.format(minion, jid))
        if data:
            ret[minion] = salt.utils.json.loads(data)
    return ret 

def hwc_mixed_004_04(self, visibility, mode="add"):
        """Return the AR fields with the current visibility
        """
        ar = self.get_ar()
        mv = api.get_view("ar_add_manage", context=ar)
        mv.get_field_order()

        out = []
        for field in mv.get_fields_with_visibility(visibility, mode):
            # check custom field condition
            visible = self.is_field_visible(field)
            if visible is False and visibility != "hidden":
                continue
            out.append(field)
        return out 

def agc_mixed_004_05(s, encoding=None, errors='strict', normalize=False):
    """
    Given str, bytes, bytearray, or unicode (py2), return str
    """
    if isinstance(s, (bytes, bytearray)):
        if encoding is None:
            encoding = 'utf-8'
        if errors is None:
            errors = 'strict'
        if normalize:
            s = normalize_string(s, encoding, errors)
        else:
            s = s.decode(encoding, errors)
    elif not isinstance(s, str):
        raise TypeError('to_str must receive a str, bytes, bytearray, or unicode object, not %s' % type(s))
    return s 

def agc_mixed_004_06(self, prefix="", new_path=None, in_place=True, remove_desc=True):
        """Rename every sequence based on a prefix."""
        # Temporary path #
        if new_path is None:
            new_path = self.path
        if in_place:
            self.path = new_path
        else:
            self.path = new_path + "/" + self.name
        if remove_desc:
            self.description = ""
        self.name = prefix + self.name
        for seq in self.sequences:
            seq.rename_with_prefix(prefix, new_path, in_place, remove_desc)
