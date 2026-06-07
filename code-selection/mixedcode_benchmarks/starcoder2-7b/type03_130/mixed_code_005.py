def hwc_mixed_005_01(area):
    """Return the cf grid mapping for the geos projection."""
    proj_dict = area.proj_dict
    args = dict(perspective_point_height=proj_dict.get('h'),
                latitude_of_projection_origin=proj_dict.get('lat_0'),
                longitude_of_projection_origin=proj_dict.get('lon_0'),
                grid_mapping_name='geostationary',
                semi_major_axis=proj_dict.get('a'),
                semi_minor_axis=proj_dict.get('b'),
                sweep_axis=proj_dict.get('sweep'),
                )
    return args 

def hwc_mixed_005_02(self):
        """Get the function pointer."""
        cmpfunc = ctypes.CFUNCTYPE(ctypes.c_int,
                                   WPARAM,
                                   LPARAM,
                                   ctypes.POINTER(KBDLLHookStruct))
        return cmpfunc(self.handle_input) 

def hwc_mixed_005_03(self, class_name, names):
        """
        Removes multiple components from the network.

        Removes them from component DataFrames.

        Parameters
        ----------
        class_name : string
            Component class name
        name : list-like
            Component names

        Examples
        --------
        >>> network.mremove("Line", ["line x", "line y"])

        """

        if class_name not in self.components:
            logger.error("Component class {} not found".format(class_name))
            return None

        if not isinstance(names, pd.Index):
            names = pd.Index(names)

        cls_df = self.df(class_name)

        cls_df.drop(names, inplace=True)

        pnl = self.pnl(class_name)

        for df in itervalues(pnl):
            df.drop(df.columns.intersection(names), axis=1, inplace=True) 

def agc_mixed_005_04(matched_filenames, cache_dir, show_lint_files):
    """Run spellcheck-linter on matched_filenames."""
    if not matched_filenames:
        return

    # We need to create a temporary directory for the cache.
    # We can't use the cache_dir because it's a symlink.
    cache_dir = tempfile.mkdtemp()
    try:
        # Run the linter.
        spellcheck_linter.main(
            matched_filenames,
            cache_dir=cache_dir,
            show_lint_files=show_lint_files,
        )
    finally:
        shutil.rmtree(cache_dir) 

def agc_mixed_005_05(self, nexus_host, vlanid, intf_type,
                                  interface, is_native):
        """Disable a VLAN on a trunk interface."""

        if intf_type == "ethernet":
            vlan_intf = "vlan" + vlanid
        else:
            vlan_intf = "vlan" + vlanid + "." + interface

        if is_native:
            cmd = "no switchport trunk allowed vlan add " + vlan_intf
        else:
            cmd = "switchport trunk allowed vlan remove " + vlan_intf

        self.execute_command(nexus_host, cmd) 

def agc_mixed_005_06(sid_or_accessor, start=None, end=None):
    """terminal and datamgr are mutually exclusive.

    :param sid_or_accessor: security identifier or SidAccessor from DataManager
    :param start:
    :param end:
    :return:
    """
    if isinstance(sid_or_accessor, SidAccessor):
        sid = sid_or_accessor.sid
    else:
        sid = sid_or_accessor

    if start is None:
        start = pd.Timestamp('1900-01-01')
    if end is None:
        end = pd.Timestamp.now()

    if isinstance(sid, str):
        sid = sid.upper()

    if sid.startswith('BBG'):
        return load_bbg_generic_sid(sid, start, end)
    elif sid.startswith('BLOOMBERG'):
        return load_bloomberg_generic_sid(sid, start, end)
    else:
        raise ValueError('Unknown SID: %s' % sid)
