def hwc_mixed_001_01(self):
        """
        Stop the interface

        :rtype: None
        """
        self.debug("()")
        # Stop the plugins
        for plugin in self.plugins:
            try:
                plugin.stop()
            except:
                self.exception(u"Failed to stop plugin {}".format(plugin.name))
        super(CrowdController, self).stop() 

def agc_mixed_001_02(gandi, resource, cmdline, kernel, name, size,
           snapshotprofile, delete_snapshotprofile, background):
    """ Update a disk.

    Resource can be a disk name, or ID
    """
    resource_id = gandi.get_resource_id(resource)
    params = {
        'name': name,
        'size': size,
        'snapshot_profile': snapshotprofile,
        'background': background
    }
    if delete_snapshotprofile:
        params['delete_snapshot_profile'] = True

    # Filter out None values to avoid overwriting with nulls if not intended
    params = {k: v for k, v in params.items() if v is not None}

    return gandi.update_disk(resource_id, params, cmdline, kernel) 

def agc_mixed_001_03(species, release=None, ftp=None):
    """Returns the URL for a cDNA file hosted on the Ensembl FTP server.

    Parameters
    ----------
    species: str
        The scientific name of the species. It should be all lower-case,
        and the genus and species parts should be separated by an underscore
        (e.g., "homo_sapiens").
    release: int or ``None``, optional
        The Ensembl release number. If ``None``, the latest release is used.
        [None]
    ftp: ftplib.FTP or ``None``, optional
        The FTP connection. If ``None``, create a new connection. [None]
    """    
    #species_list, release=None, ftp=None

    # type checks
    if release is None:
        import ftplib
        with ftplib.FTP("ftp.ensembl.org") as conn:
            conn.cwd("pub")
            releases = sorted([d for d in conn.nlst() if d.startswith("release-")], reverse=True)
            release = int(releases[0].split("-")[1])

    base_url = "ftp://ftp.ensembl.org/pub"
    if release:
        base_url += f"/release-{release}"

    return f"{base_url}/cDNA/{species}/cDNA.fa.gz" 

async def hwc_mixed_001_04(self, frame):
        """Handle incoming API frame, return True if this was the expected frame."""
        if not isinstance(frame, FramePasswordEnterConfirmation):
            return False
        if frame.status == PasswordEnterConfirmationStatus.FAILED:
            PYVLXLOG.warning('Failed to authenticate with password "%s****"', self.password[:2])
            self.success = False
        if frame.status == PasswordEnterConfirmationStatus.SUCCESSFUL:
            self.success = True
        return True 

def agc_mixed_001_05(self, switches=None):
        """Refresh data on switch interfaces' port group membership"""
        if switches is None:
            switches = self.get_switches()

        for switch in switches:
            port_groups = switch.get_port_groups()
            for pg in port_groups:
                for port in pg.get_ports():
                    self.update_port_membership(switch.id, port.id, pg.id) 

def hwc_mixed_001_06(self, config_path, quiet=False, bootstrap_server=False,
                   create_client=False):
        """Get a cached client for a project, otherwise create one."""
        client = None
        abs_path = os.path.abspath(config_path)
        if abs_path in self.clients:
            client = self.clients[abs_path]
        elif create_client:
            client = self.create_client(config_path)
            if client.setup(quiet=quiet, bootstrap_server=bootstrap_server):
                self.clients[abs_path] = client
        return client
