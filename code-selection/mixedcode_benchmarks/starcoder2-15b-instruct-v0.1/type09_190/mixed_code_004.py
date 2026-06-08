def hwc_mixed_004_01(self, channel, value, unit='A'):
        """Setting current of current source
        """
        dac_offset = self._ch_cal[channel]['DAC']['offset']
        dac_gain = self._ch_cal[channel]['DAC']['gain']
        if unit == 'raw':
            value = value
        elif unit == 'A':
            value = int((-value * 1000000 - dac_offset) / dac_gain)  # fix sign of output
        elif unit == 'mA':
            value = int((-value * 1000 - dac_offset) / dac_gain)  # fix sign of output
        elif unit == 'uA':
            value = int((-value - dac_offset) / dac_gain)  # fix sign of output
        else:
            raise TypeError("Invalid unit type.")

        self._set_dac_value(channel=channel, value=value) 

def agc_mixed_004_02(self, device):
        """ Updates the device information based on files from its 'mount_point'
            @param device Dictionary containing device information
        """
        device_name = device['name']
        device_mount_point = device['mount_point']
        device_files = os.listdir(device_mount_point)
        for file_name in device_files:
            file_path = os.path.join(device_mount_point, file_name)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_modification_time = os.path.getmtime(file_path)
                device[file_name] = {
                   'size': file_size,
                   'modification_time': file_modification_time
                } 

def hwc_mixed_004_03(traceback):
    """
    For internal use only (until further notice)
    """
    if email().format == 'html':
        try:
            from pygments import highlight
            from pygments.lexers import PythonTracebackLexer
            from pygments.formatters import HtmlFormatter
            with_pygments = True
        except ImportError:
            with_pygments = False

        if with_pygments:
            formatter = HtmlFormatter(noclasses=True)
            wrapped = highlight(traceback, PythonTracebackLexer(), formatter)
        else:
            wrapped = '<pre>%s</pre>' % traceback
    else:
        wrapped = traceback

    return wrapped 

def agc_mixed_004_04(self, subnetId, domainId):
        """ Function removeDomain
        Delete a domain from a subnet

        @param subnetId: The subnet Id
        @param domainId: The domainId to be attached wiuth the subnet
        @return RETURN: boolean
        """
        try:
            subnet = self.getSubnet(subnetId)
            if subnet is None:
                return False

            if domainId in subnet.domains:
                subnet.domains.remove(domainId)
                subnet.save()
                return True
            else:
                return False
        except Exception as e:
            log.error("Exception: %s" % str(e))
            return False 

def agc_mixed_004_05(self, garbage=0, clean=0, deflate=0, ascii=0, expand=0, linear=0, pretty=0, decrypt=1):
        """Write document to a bytes object."""

        if garbage:
            return b'GARBAGE'
        if clean:
            return b'CLEAN'
        if deflate:
            return b'DEFLATE'
        if ascii:
            return b'ASCII'
        if expand:
            return b'EXPAND'
        if linear:
            return b'LINEAR'
        if pretty:
            return b'PRETTY'
        if decrypt:
            return b'DECRYPT'
        return b'' 

def hwc_mixed_004_06(target, mobile, target_i=0, mobile_i=0):
    """Aligns one Polypeptide (mobile) to another (target).

    Notes
    -----
    This function directly modifies atoms of the mobile Polypeptide!
    It does not return a new object.

    Parameters
    ----------
    target : Polypeptide
        Polypeptide to be aligned to.
    mobile : Polypeptide
        Polypeptide to be moved during alignment.
    target_i : int, optional
        Index of `Residue` in target to align to.
    mobile_i : int, optional
        Index of `Residue` in mobile to be aligned.
    """
    # First, align N->CA vectors.
    s1, e1, s2, e2 = [x._vector
                      for x in [mobile[mobile_i]['N'], mobile[mobile_i]['CA'],
                                target[target_i]['N'], target[target_i]['CA']]]
    translation, angle, axis, point = find_transformations(
        s1, e1, s2, e2, radians=False)
    # Rotation first, Then translation.
    mobile.rotate(angle=angle, axis=axis, point=point, radians=False)
    mobile.translate(vector=translation)
    # Second, rotate about N->CA axis to align CA->C vectors.
    angle = dihedral(mobile[mobile_i]['C'], mobile[mobile_i]
                     ['N'], mobile[mobile_i]['CA'], target[target_i]['C'])
    axis = target[target_i]['CA'] - target[target_i]['N']
    point = target[target_i]['N']._vector
    mobile.rotate(angle=angle, axis=axis, point=point)
    return
