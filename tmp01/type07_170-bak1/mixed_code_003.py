def agc_mixed_003_01(certificate):
    """
    Returns a dict containing details of a certificate. Input can be a PEM
    string or file path.

    certificate:
        The certificate to be read. Can be a path to a certificate file, or
        a string containing the PEM formatted text of the certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_certificate /etc/pki/mycert.crt
    """
    if os.path.isfile(certificate):
        with salt.utils.files.fopen(certificate, "r") as _certificate:
            certificate = _certificate.read()
    try:
        cert = M2Crypto.X509.load_cert_string(certificate)
    except M2Crypto.X509.X509Error as err:
        raise CommandExecutionError(err)
    return {
        "subject": cert.get_subject().as_text(),
        "issuer": cert.get_issuer().as_text(),
        "not_before": cert.get_not_before().as_tuple(),
        "not_after": cert.get_not_after().as_tuple(),
        "serial_number": cert.get_serial_number(),
        "version": cert.get_version(),
        "signature_algorithm": cert.get_signature_algorithm(),
        "signature": cert.get_signature(),
        "public_key": cert.get_pubkey().as_text(),
        "extensions": cert.get_extensions(),
    } 

def hwc_mixed_003_02(self, block, file_info):
        """
        new content from file_info can be added into block iff
        - file count limit hasn't been reached for the block
        - there is enough space to completely fit the info into the block
        - OR the info can be split and some info can fit into the block
        """
        return ((self._max_files_per_container == 0 or self._max_files_per_container > len(block.content_file_infos))
                and (self.does_content_fit(file_info, block)
                     or
                     # check if we can fit some content by splitting the file
                     # Note: if max size was unlimited, does_content_fit would have been True
                     (block.content_size < self._max_container_content_size_in_bytes
                      and (self._should_split_small_files or not self._is_small_file(file_info))))) 

def hwc_mixed_003_03(self, attr_name, prefix=None):
        """Write attribute's value to a file.

        :param str attr_name:
            Attribute's name to be logged

        :param str prefix:
            Optional. Attribute's name that is prefixed to logging message,
            defaults to ``None``.

        :returns: message written to file
        :rtype: str
        """
        if self._folder is None:
            return

        separator = "\t"
        attr = getattr(self.obj, attr_name)
        if hasattr(attr, '__iter__'):
            msg = separator.join([str(e) for e in attr])
        else:
            msg = str(attr)

        if prefix is not None:
            msg = "{}\t{}".format(getattr(self.obj, prefix), msg)

        path = self.get_file(attr_name)
        with open(path, 'a') as f:
            f.write("{}\n".format(msg))

        return msg 

def agc_mixed_003_04(name, value, persist=False):
    """
    Set up an SELinux boolean

    name
        The name of the boolean to set

    value
        The value to set on the boolean

    persist
        Defaults to False, set persist to true to make the boolean apply on a
        reboot
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if __salt__["selinux.getboolean"](name) == value:
        ret["comment"] = "SELinux boolean {} already set to {}".format(name, value)
        return ret

    if __opts__["test"]:
        ret["comment"] = "SELinux boolean {} will be set to {}".format(name, value)
        ret["result"] = None
        return ret

    if __salt__["selinux.setboolean"](name, value, persist):
        ret["comment"] = "SELinux boolean {} set to {}".format(name, value)
        ret["changes"] = {"old": __salt__["selinux.getboolean"](name), "new": value}
    else:
        ret["comment"] = "Failed to set SELinux boolean {} to {}".format(name, value)
        ret["result"] = False

    return ret 

def hwc_mixed_003_05(self):
    """
    Export a DataFrame from the front-end visualization. For instance, a user
    can filter to show only a single cluster using the dendrogram and then
    get a dataframe of this cluster using the widget_df method.
    """

    if hasattr(self, 'widget_instance') == True:

      if self.widget_instance.mat_string != '':

        tmp_net = deepcopy(Network())

        df_string = self.widget_instance.mat_string

        tmp_net.load_file_as_string(df_string)

        df = tmp_net.export_df()

        return df

      else:
        return self.export_df()

    else:
      if hasattr(self, 'widget_class') == True:
        print('Please make the widget before exporting the widget DataFrame.')
        print('Do this using the widget method: net.widget()')

      else:
        print('Can not make widget because Network has no attribute widget_class')
        print('Please instantiate Network with clustergrammer_widget using: Network(clustergrammer_widget)') 

def agc_mixed_003_06(self, conn):
        """
        Create the version table into an already populated database
        and insert the base script.

        :param conn: a DB API 2 connection
        """
        conn.execute("""
            CREATE TABLE version (
                id INTEGER PRIMARY KEY,
                version TEXT NOT NULL,
                script TEXT NOT NULL,
                UNIQUE (version)
            );
        """)
        conn.execute("""
            INSERT INTO version (version, script)
            VALUES (?, ?);
        """, ("0.0.0", "base"))
