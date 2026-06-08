def agc_mixed_003_01(input, format=None):
    """ Returns a case object from the given input file object. The data
    format may be optionally specified.
    """
    # Map of data file types to readers.
    if format is None:
        format = input.readline().strip()
    if format == 'json':
        return read_json(input)
    elif format == 'yaml':
        return read_yaml(input)
    elif format == 'xml':
        return read_xml(input)
    elif format == 'csv':
        return read_csv(input)
    elif format == 'tsv':
        return read_tsv(input)
    elif format == 'xlsx':
        return read_xlsx(input)
    elif format == 'xls':
        return read_xls(input)
    elif format == 'txt':
        return read_txt(input)
    else:
        raise ValueError('Unknown format: %s' % format) 

def hwc_mixed_003_02(self, value, store_type):
        """Save the key value base on it's storage type."""
        self._store_type = store_type
        if store_type == PUBLIC_KEY_STORE_TYPE_HEX:
            self._value = value.hex()
        elif store_type == PUBLIC_KEY_STORE_TYPE_BASE64:
            self._value = b64encode(value).decode()
        elif store_type == PUBLIC_KEY_STORE_TYPE_BASE85:
            self._value = b85encode(value).decode()
        elif store_type == PUBLIC_KEY_STORE_TYPE_JWK:
            # TODO: need to decide on which jwk library to import?
            raise NotImplementedError
        else:
            self._value = value
        return value 

def agc_mixed_003_03(self, data):
        """ Processes a received STATUS message and notifies listeners. """
        if data.get('status') == 'OK':
            self._status = 'OK'
        elif data.get('status') == 'ERROR':
            self._status = 'ERROR'
        elif data.get('status') == 'WARNING':
            self._status = 'WARNING'
        elif data.get('status') == 'UNKNOWN':
            self._status = 'UNKNOWN'
        else:
            self._status = 'UNKNOWN'

        self._status_message = data.get('message')
        self._status_code = data.get('code')
        self._status_data = data.get('data')

        self._notify_status_listeners() 

def agc_mixed_003_04(self, release):
        """Copy the workfile of the given release to the releasefile location

        This is inteded to be used in a action unit.

        :param release: the release with the release and workfile
        :type release: :class:`Release`
        :returns: an action status
        :rtype: :class:`ActionStatus`
        :raises: None
        """
        if release.workfile is None:
            return ActionStatus.failure("No workfile for release")

        if release.releasefile is not None:
            return ActionStatus.failure("Releasefile already exists")

        if release.workfile.path is None:
            return ActionStatus.failure("No path for workfile")

        if not os.path.exists(release.workfile.path):
            return ActionStatus.failure("Workfile does not exist")

        try:
            shutil.copy(release.workfile.path, release.releasefile.path)
        except Exception as e:
            return ActionStatus.failure(str(e))

        return ActionStatus.success() 

def hwc_mixed_003_05(fin_src, fout):
    """Download a file from an ftp server"""
    assert fin_src[:6] == 'ftp://', fin_src
    dir_full, fin_ftp = os.path.split(fin_src[6:])
    pt0 = dir_full.find('/')
    assert pt0 != -1, pt0
    ftphost = dir_full[:pt0]
    chg_dir = dir_full[pt0+1:]
    print('FTP RETR {HOST} {DIR} {SRC} -> {DST}'.format(
        HOST=ftphost, DIR=chg_dir, SRC=fin_ftp, DST=fout))
    ftp = FTP(ftphost)  # connect to host, default port      ftp.ncbi.nlm.nih.gov
    ftp.login()         # user anonymous, passwd anonymous@
    ftp.cwd(chg_dir)    # change into "debian" directory     gene/DATA
    cmd = 'RETR {F}'.format(F=fin_ftp)   #                   gene2go.gz
    ftp.retrbinary(cmd, open(fout, 'wb').write)  #           /usr/home/gene2go.gz
    ftp.quit() 

def hwc_mixed_003_06(self):
        """Returns tuple key rect of above left cell"""

        key_above_left = self.row - 1, self.col - 1, self.tab

        border_width_right = \
            float(self.cell_attributes[key_above_left]["borderwidth_right"]) \
            / 2.0
        border_width_bottom = \
            float(self.cell_attributes[key_above_left]["borderwidth_bottom"]) \
            / 2.0

        rect_above_left = (self.x-border_width_right,
                           self.y-border_width_bottom,
                           border_width_right, border_width_bottom)
        return key_above_left, rect_above_left
