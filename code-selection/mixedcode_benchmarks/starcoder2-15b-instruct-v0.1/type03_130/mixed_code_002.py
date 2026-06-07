def hwc_mixed_002_01(img_url, img_size=300):
    """
    Resize a program's thumbnail to the desired dimension
    """
    match = re.match(r'.+/(\d+)x(\d+)/.+', img_url)
    if not match:
        _LOGGER.warning('Could not compute current image resolution of %s',
                        img_url)
        return img_url
    res_x = int(match.group(1))
    res_y = int(match.group(2))
    # aspect_ratio = res_x / res_y
    target_res_y = int(img_size * res_y / res_x)
    return re.sub(
        r'{}x{}'.format(res_x, res_y),
        r'{}x{}'.format(img_size, target_res_y),
        img_url) 

def agc_mixed_002_02(context, request):
    """ Read Shimadzu GCMS-TQ8030 GC/MS/MS analysis results
    """
    data = request['data']
    results = []
    for line in data.splitlines():
        if line.startswith('Name'):
            continue
        parts = line.split('\t')
        if len(parts) < 10:
            continue
        name = parts[0]
        rt = float(parts[1])
        mz = float(parts[2])
        intensity = float(parts[3])
        results.append((name, rt, mz, intensity))
    return results 

def hwc_mixed_002_03(self):
        """Returns a simple key-value map for easy access to data paths"""
        paths = { }
        try:
            data = self._config['data']
            for k in data:
                paths[k] = data[k]['path']
        except KeyError as e:
            raise AitConfigMissing(e.message)
        except Exception as e:
            raise AitConfigError('Error reading data paths: %s' % e)

        return paths 

def agc_mixed_002_04(self):
        """
        Used for moving to next business day.
        """
        while True:
            if self.is_bday():
                self.date += datetime.timedelta(days=1)
                break
            else:
                self.date += datetime.timedelta(days=1)
                while not self.is_bday():
                    self.date += datetime.timedelta(days=1) 

def hwc_mixed_002_05(
            self):
        """
        *fill placeholders from the placeholders in the settings file*
        """
        self.log.info(
            'starting the ``_fill_placeholders_from_settings`` method')

        for k, v in self.phDict.iteritems():
            if k in self.settings["frankenstein"]["fixed placeholders"].keys():
                self.phDict[k] = self.settings[
                    "frankenstein"]["fixed placeholders"][k]

        self.log.info(
            'completed the ``_fill_placeholders_from_settings`` method')
        return None 

def agc_mixed_002_06( self, path_info, blockchain_name, blockheight ):
        """
        Get the name's historic name operations
        Reply the list of nameops at the given block height
        Reply 404 for blockchains other than those supported
        Reply 502 for any error we have in talking to the blockstack server
        """
        if blockchain_name not in self.supported_blockchains:
            return 404
        try:
            blockheight = int(blockheight)
        except ValueError:
            return 502
        try:
            nameops = self.blockstack_client.get_nameops(blockchain_name, blockheight)
        except Exception:
            return 502
        return nameops
