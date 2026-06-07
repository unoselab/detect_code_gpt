def agc_mixed_005_01(self):
        """Auto-connect slot activated when north arrow checkbox is toggled."""
        if self.ui.northArrow.isChecked():
            self.ui.northArrow.setEnabled(False)
            self.ui.northArrow.setChecked(True)
            self.ui.northArrow.setEnabled(True)
            self.ui.northArrow.setChecked(False)
        else:
            self.ui.northArrow.setEnabled(False)
            self.ui.northArrow.setChecked(True)
            self.ui.northArrow.setEnabled(True)
            self.ui.northArrow.setChecked(False) 

def agc_mixed_005_02(self, time_to, event_dict):
        """
        Checks if the time until an event starts is less than or equal to the
        warn_threshold. If True, issue a warning with self.py3.notify_user.
        """
        if time_to <= self.warn_threshold:
            self.py3.notify_user(
                "{} is in {} minutes".format(
                    event_dict['name'],
                    int(time_to)
                )
            ) 

def agc_mixed_005_03(self, timeout=None):
        """
        Gets the properties of a storage account's File service, including
        Azure Storage Analytics.

        :param int timeout:
            The timeout parameter is expressed in seconds.
        :return: The file service properties.
        :rtype:
            :class:`~azure.storage.common.models.ServiceProperties`
        """
        request = HTTPRequest()
        request.method = 'GET'
        request.host_locations = self._primary_hostname
        request.path = '/'
        request.query = {
            'restype': 'service',
            'comp': 'properties',
        }
        request.headers = self._get_service_properties_headers()
        request.timeout = timeout

        return self._perform_request(request) 

def hwc_mixed_005_04(self, results):
        """
        Display results.

        :param status: Response status
        :param results: Response data, messages.
        """
        messages = []
        for msg in results:
            msg = CheckerMessage(*msg)
            if msg.line >= self.editor.blockCount():
                msg.line = self.editor.blockCount() - 1
            block = self.editor.document().findBlockByNumber(msg.line)
            msg.block = block
            messages.append(msg)
        self.add_messages(messages) 

def hwc_mixed_005_05():
    """
    Returns all key pairs for region
    """
    region_keys = {}
    for r in boto3.client('ec2', 'us-west-2').describe_regions()['Regions']:
        region = r['RegionName']
        client = boto3.client('ec2', region_name=region)
        try:
            pairs = client.describe_key_pairs()
            if pairs:
                region_keys[region] = pairs
        except Exception as e:
            app.logger.info(e)
    return region_keys 

def hwc_mixed_005_06(kwargs=None, conn=None, call=None):
    """
    .. versionadded:: 2015.8.0

    Return information about a management_certificate

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_management_certificate my-azure name=my_management_certificate \\
            thumbalgorithm=sha1 thumbprint=0123456789ABCDEF
    """
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_management_certificate function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if kwargs is None:
        kwargs = {}

    if 'thumbprint' not in kwargs:
        raise SaltCloudSystemExit('A thumbprint must be specified as "thumbprint"')

    data = conn.get_management_certificate(kwargs['thumbprint'])
    return object_to_dict(data)
